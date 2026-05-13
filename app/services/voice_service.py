"""
VOXAORA Voice Pipeline — Professional Arabic Customer Service Agent
"""
import time
import json
import random
import re
from typing import Dict, Any, List, BinaryIO, Optional
from groq import AsyncGroq
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# ─── LLM System Prompt ────────────────────────────────────────────────────────
INTENT_PROMPT = """أنت مساعد ذكي لتطبيق VOXAORA للتوصيل في اليمن (صنعاء).
مهمتك: تحليل طلب العميل واستخراج المعلومات التالية بصيغة JSON فقط.

الأصناف المتاحة: restaurant, grocery, coffee, bakery, other

أعد JSON بهذا الشكل:
{
  "category": "restaurant",
  "items": [
    {"name": "اسم المنتج بالعربي", "name_en": "product name in english", "quantity": 1, "size": null}
  ],
  "constraints": {
    "max_delivery_time_minutes": null,
    "max_price": null,
    "min_rating": null
  },
  "is_reorder": false,
  "confidence": 0.95
}

قواعد مهمة:
- أعد JSON فقط بلا أي نص خارجه
- category يجب أن يكون واحداً من: restaurant, grocery, coffee, bakery, other
- إذا ذكر مطعم أو أكل (شاورما، مندي، دجاج، برجر، بيتزا، زنجر، سمبوسة، فول، فتة، عصيد، بريياني، مرق، ثريد، مطعم) → category: restaurant
- إذا ذكر قهوة، شاي، كافيه، عصير، مشروبات → category: coffee
- إذا ذكر حلويات، كيك، مخبوزات، لحوح، فطير، فطور → category: bakery أو restaurant
- إذا ذكر بقالة، سوبرماركت، خضار، حليب، بيض، تسوق → category: grocery
- اللهجة اليمنية: (أبي، أبغى، بغيت، أريد، عايز، ودي، حابب، مادري، عندكم، جيب، هات)
- مفردات يمنية: لحوح=فطير يمني، سلتة=مرق وحلبة، مرق=شوربة، بنطلون=لا علاقة بالطعام
- الأسعار بالريال اليمني (ريال)
- افهم المختصرات والأسماء المحلية
"""

# ─── Professional Arabic Response Library ─────────────────────────────────────
GREETINGS = [
    "أهلاً وسهلاً! معك فوكسورا. إيش تبغى اليوم؟",
    "يا هلا! أنا مساعدك في فوكسورا، تفضل قل طلبك.",
    "مرحبا! فوكسورا في خدمتك. إيش تحب تطلب؟",
    "أهلاً! قل لي طلبك وأنا أجيبه لك بأسرع وقت.",
    "تفضل! فوكسورا جاهز. إيش تبي؟",
]

PROCESSING = [
    "تمام، فاهم عليك. أبحث لك الآن عن أفضل الخيارات...",
    "ماشي، لحظة أشوف لك الخيارات المتاحة...",
    "واضح، أبحث لك الحين...",
    "أوكي! دقيقة أجيب لك أفضل خيار...",
]

CONFIRM_MSGS = [
    "تمام! تم تأكيد طلبك من {merchant}. يوصلك إن شاء الله خلال {eta} دقيقة. رقم الطلب: {order}",
    "ابشر! طلبك من {merchant} في الطريق. يصل خلال {eta} دقيقة. شكراً لاستخدامك فوكسورا.",
    "ممتاز! طلبك مؤكد من {merchant}، سيصل خلال {eta} دقيقة بإذن الله.",
    "تمام والله! أكدنا طلبك من {merchant}، وقت التوصيل حوالي {eta} دقيقة.",
]

NO_RESULTS = [
    "ما لقينا {item} متوفر قريب منك الحين. تبغى شيء ثاني؟",
    "للأسف ما عندنا {item} قريبك دلوقتي. جرب طلب آخر؟",
    "ما فيه {item} متاح الحين. تبي بديل؟",
]

UNAVAILABLE = [
    "عذراً، {item} مو متوفر الحين. تبي بديل؟",
    "{item} ما هو متاح دلوقتي. تبي شيء مشابه؟",
]

# ─── Transcript validation ─────────────────────────────────────────────────────
def _is_valid_arabic_transcript(text: str) -> bool:
    """Returns True if transcript looks like real Arabic/English speech."""
    if not text or len(text.strip()) < 2:
        return False
    clean = text.strip()
    arabic  = sum(1 for c in clean if '؀' <= c <= 'ۿ')
    latin   = sum(1 for c in clean if c.isascii() and c.isalpha())
    total   = max(1, len(clean.replace(' ', '')))
    # Accept if at least 25% is recognizable language characters
    return (arabic + latin) / total >= 0.25


class VoiceService:
    def __init__(self):
        key = (settings.GROQ_API_KEY or "").strip()
        self.client: Optional[AsyncGroq] = AsyncGroq(api_key=key) if key else None
        if self.client:
            logger.info("voice_groq_ready", stt="whisper-large-v3", nlu="llama-3.3-70b-versatile")
        else:
            logger.info("voice_mock_mode")

    # ── STT ──────────────────────────────────────────────────────────────────
    async def transcribe_audio(self, audio_file: BinaryIO, filename: str = "audio.webm") -> Dict[str, Any]:
        if not self.client:
            return {"text": "", "language": "ar", "confidence": 0.0, "processing_ms": 0}

        start = time.time()
        try:
            response = await self.client.audio.transcriptions.create(
                file=(filename, audio_file, "audio/webm"),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="ar",        # ← Force Arabic, prevents hallucination
                temperature=0.0,
            )
            text = (response.text or "").strip()
            ms   = int((time.time() - start) * 1000)

            if not _is_valid_arabic_transcript(text):
                logger.warning("whisper_invalid_transcript", text=text[:50])
                return {"text": "", "language": "ar", "confidence": 0.0, "processing_ms": ms}

            return {"text": text, "language": "ar", "confidence": 0.95, "processing_ms": ms}

        except Exception as e:
            logger.error("groq_stt_error", error=str(e))
            raise

    # ── NLU ──────────────────────────────────────────────────────────────────
    async def extract_intent(self, transcript: str, user_language: str = "ar") -> Dict[str, Any]:
        if not self.client:
            return self._mock_intent(transcript)
        try:
            resp = await self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": INTENT_PROMPT},
                    {"role": "user",   "content": transcript},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=600,
            )
            result = json.loads(resp.choices[0].message.content)
            result["raw_query"] = transcript.lower().strip()
            result["language"]  = "ar"   # always Arabic
            return result
        except Exception as e:
            logger.warning("groq_nlu_error", error=str(e))
            return self._mock_intent(transcript)

    # ── Response builders ─────────────────────────────────────────────────────
    def get_greeting(self, language: str = "ar") -> str:
        return random.choice(GREETINGS)

    def get_processing_phrase(self, language: str = "ar") -> str:
        return random.choice(PROCESSING)

    def build_results_response(self, results: List[Dict], language: str = "ar",
                               intent: Dict = None) -> str:
        """Always responds in Arabic regardless of language param."""
        if not results:
            item_name = ""
            if intent and intent.get("items"):
                item_name = intent["items"][0].get("name", "")
            return random.choice(NO_RESULTS).format(item=item_name or "ما طلبته")

        first  = results[0]
        fname  = first.get("name_ar") or first.get("name", "")
        feta   = first.get("estimated_eta_minutes", 30)
        ffee   = first.get("delivery_fee", 0)
        fitems = first.get("items", [])

        # Build item mentions for first merchant
        item_text = ""
        if fitems:
            parts = []
            for p in fitems[:2]:
                pname  = p.get("name_ar") or p.get("name", "")
                pprice = p.get("price", 0)
                if pname and pprice:
                    parts.append(f"{pname} بـ {pprice:.0f} ريال")
            if parts:
                item_text = " و".join(parts)

        # First merchant
        if item_text:
            response = f"وجدت لك {item_text} من {fname}، "
        else:
            response = f"وجدت لك {fname}، "

        response += f"يوصل خلال {feta} دقيقة"
        response += " والتوصيل مجاني!" if ffee == 0 else f"."

        # Second merchant
        if len(results) > 1:
            second = results[1]
            sname  = second.get("name_ar") or second.get("name", "")
            seta   = second.get("estimated_eta_minutes", 30)
            sitems = second.get("items", [])
            if sitems:
                sp     = sitems[0]
                spname = sp.get("name_ar") or sp.get("name", "")
                sprice = sp.get("price", 0)
                if spname and sprice:
                    response += f" وعندنا كمان {spname} من {sname} بـ {sprice:.0f} ريال في {seta} دقيقة."
                else:
                    response += f" وكمان {sname} التوصيل {seta} دقيقة."
            else:
                response += f" وكمان {sname} في {seta} دقيقة."

        # Third
        if len(results) > 2:
            third = results[2]
            tname = third.get("name_ar") or third.get("name", "")
            teta  = third.get("estimated_eta_minutes", 30)
            response += f" والخيار الثالث {tname} في {teta} دقيقة."

        response += " أي خيار تبغى؟"
        return response

    def build_confirmation_response(self, merchant_name: str, eta: int,
                                    language: str = "ar", order_number: str = None) -> str:
        msg = random.choice(CONFIRM_MSGS).format(
            merchant=merchant_name, eta=eta,
            order=order_number or "---"
        )
        return msg

    def build_unavailable_response(self, item_name: str,
                                   alternatives: List[str] = None, language: str = "ar") -> str:
        msg = random.choice(UNAVAILABLE).format(item=item_name)
        if alternatives:
            msg += f" البدائل المتاحة: {', '.join(alternatives[:3])}."
        return msg

    def build_no_results_response(self, item_name: str = "", language: str = "ar") -> str:
        return random.choice(NO_RESULTS).format(item=item_name or "ما طلبته")

    def build_selection_response(self, index: int, language: str = "ar") -> str:
        ordinals = ["الأول", "الثاني", "الثالث"]
        label = ordinals[index] if index < len(ordinals) else f"رقم {index+1}"
        return random.choice([
            f"ممتاز! جارٍ تأكيد طلبك من الخيار {label}...",
            f"تمام! أؤكد الطلب من {label} الحين...",
            f"أحسنت! جارٍ الطلب من {label}...",
        ])

    # ── Follow-up intent (multi-turn) ────────────────────────────────────────
    async def extract_followup_intent(
        self,
        transcript: str,
        previous_transcript: str,
        previous_results: List[Dict],
    ) -> Dict[str, Any]:
        """
        Given a follow-up utterance + previous results context, return either:
          {"action": "select", "index": 0|1|2}  — user picked a specific result
          {"action": "search", ...regular intent fields}  — user wants a new search
        """
        if not self.client:
            return self._mock_followup_intent(transcript, previous_results)

        # Build numbered list of previous results for the LLM
        options_text = "\n".join([
            f"{i+1}. {r.get('name_ar') or r.get('name', '')} — {r.get('estimated_eta_minutes', '?')}د"
            f" — {r.get('delivery_fee', 0):.0f} ر.س"
            for i, r in enumerate(previous_results[:3])
        ])

        system = f"""أنت مساعد ذكي لتطبيق VOXAORA للتوصيل.
الطلب السابق للمستخدم: "{previous_transcript}"
الخيارات المعروضة عليه حالياً:
{options_text}

مهمتك: حدد ماذا يريد المستخدم الآن.

إذا كان يختار من الخيارات أو يعدّل اختياره:
- أي كلام يدل على الأول (الأول، الخيار الأول، من عندهم، منه، واحد، هذا، موافق، تمام، أوكي، نعم، ابشر) → {{"action":"select","index":0}}
- الثاني → {{"action":"select","index":1}}
- الثالث → {{"action":"select","index":2}}
- الأرخص → {{"action":"select","index":{self._min_index(previous_results,"delivery_fee")}}}
- الأقرب → {{"action":"select","index":{self._min_index(previous_results,"distance_km")}}}
- الأسرع → {{"action":"select","index":{self._min_index(previous_results,"estimated_eta_minutes")}}}
- الأعلى تقييماً → {{"action":"select","index":{self._max_index(previous_results,"rating")}}}

إذا كان يطلب شيئاً مختلفاً تماماً → أعد JSON بتنسيق البحث العادي مع إضافة "action":"search"

أعد JSON فقط بلا أي نص إضافي."""

        try:
            resp = await self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": transcript},
                ],
                response_format={"type": "json_object"},
                temperature=0.05,
                max_tokens=300,
            )
            result = json.loads(resp.choices[0].message.content)
            result["raw_query"] = transcript.lower().strip()
            result["language"]  = "ar"
            return result
        except Exception as e:
            logger.warning("groq_followup_error", error=str(e))
            return self._mock_followup_intent(transcript, previous_results)

    @staticmethod
    def _min_index(results: List[Dict], key: str) -> int:
        if not results:
            return 0
        vals = [r.get(key, float("inf")) for r in results[:3]]
        return vals.index(min(vals))

    @staticmethod
    def _max_index(results: List[Dict], key: str) -> int:
        if not results:
            return 0
        vals = [r.get(key, 0) for r in results[:3]]
        return vals.index(max(vals))

    def _mock_followup_intent(self, transcript: str, results: List[Dict]) -> Dict[str, Any]:
        t = transcript.lower()
        SELECT_FIRST  = ["الأول","واحد","من عندهم","منه","هذا","موافق","تمام","أوكي","نعم","ابشر","اختار","اطلب"]
        SELECT_SECOND = ["الثاني","اثنين","ثاني"]
        SELECT_THIRD  = ["الثالث","ثلاثة","ثالث"]
        if any(w in t for w in SELECT_FIRST):  return {"action":"select","index":0}
        if any(w in t for w in SELECT_SECOND): return {"action":"select","index":1}
        if any(w in t for w in SELECT_THIRD):  return {"action":"select","index":2}
        if "أرخص" in t or "رخيص" in t:
            return {"action":"select","index":self._min_index(results,"delivery_fee")}
        if "أقرب" in t or "قريب" in t:
            return {"action":"select","index":self._min_index(results,"distance_km")}
        if "أسرع" in t or "سريع" in t:
            return {"action":"select","index":self._min_index(results,"estimated_eta_minutes")}
        # Default: treat as new search
        return {**self._mock_intent(transcript), "action": "search"}

    # ── Mock fallback (no API key) ─────────────────────────────────────────────
    def _mock_intent(self, transcript: str) -> Dict[str, Any]:
        t = transcript.lower()
        category = None
        if any(w in t for w in ["بقالة","سوبر","خضار","حليب","بيض","تسوق","سوق"]):
            category = "grocery"
        elif any(w in t for w in ["قهوة","كافيه","لاتيه","كابتشينو","شاي","عصير","مشروب"]):
            category = "coffee"
        elif any(w in t for w in ["حلويات","كيك","مخبوزات","لحوح","فطير","خبز"]):
            category = "bakery"
        elif any(w in t for w in ["مطعم","وجبة","أكل","طعام","بيتزا","برجر","دجاج",
                                   "شاورما","زنجر","مندي","سمبوسة","فول","فتة","عصيد",
                                   "بريياني","مرق","سلتة","ثريد","شيش","كباب","سمك"]):
            category = "restaurant"

        ITEMS = {
            "بيتزا":   ("بيتزا",    "pizza"),
            "برجر":    ("برجر",     "burger"),
            "دجاج":    ("دجاج",     "chicken"),
            "زنجر":    ("زنجر",     "zinger"),
            "شاورما":  ("شاورما",   "shawarma"),
            "مندي":    ("مندي",     "mandi"),
            "بريياني": ("بريياني",  "biryani"),
            "برياني":  ("برياني",   "biryani"),
            "سمبوسة":  ("سمبوسة",   "samboosa"),
            "فول":     ("فول",      "foul"),
            "فتة":     ("فتة",      "fatta"),
            "عصيد":    ("عصيد",     "aseed"),
            "مرق":     ("مرق",      "maraq"),
            "سلتة":    ("سلتة",     "saltah"),
            "لحوح":    ("لحوح",     "lahoh"),
            "لاتيه":   ("لاتيه",    "latte"),
            "كابتشينو":("كابتشينو", "cappuccino"),
            "قهوة":    ("قهوة",     "coffee"),
            "عصير":    ("عصير",     "juice"),
            "حليب":    ("حليب",     "milk"),
            "بيض":     ("بيض",      "eggs"),
            "خبز":     ("خبز",      "bread"),
            "كيك":     ("كيك",      "cake"),
        }
        items, seen = [], set()
        for kw, (ar, en) in ITEMS.items():
            if kw in t and en not in seen:
                seen.add(en)
                items.append({"name": ar, "name_en": en, "quantity": 1, "size": None})

        STOP = {"أريد","أبغى","ابغى","أبي","اطلب","بغيت","عايز","محتاج","ودي",
                "من","في","مع","على","و","أو","لي","هل","يا","حابب","جيب","هات"}
        if not items:
            words = [w for w in t.split() if len(w) >= 2 and w not in STOP]
            search = " ".join(words[:4]) if words else transcript[:50]
            items = [{"name": search, "name_en": search, "quantity": 1, "size": None}]

        return {
            "category": category, "items": items,
            "raw_query": t, "language": "ar",
            "constraints": {"max_delivery_time_minutes": None, "max_price": None, "min_rating": None},
            "is_reorder": False, "confidence": 0.8,
        }


voice_service = VoiceService()
