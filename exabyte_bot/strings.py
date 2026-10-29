"""ALL customer-facing text (Burmese, Myanmar Unicode — never Zawgyi).

Edit the text freely; keep the {placeholders} intact. Use t("key", name=value).
Keys are grouped by screen. Phase B/C add more keys here, never inline in code.
"""

from __future__ import annotations

BRAND = "Exabyte Digital Store"
HEADER = "✨ Exabyte Digital Store"
DIVIDER = "━━━━━━━━━━━━━━"

S: dict[str, str] = {
    # --- general ---
    "tagline": "လုံခြုံ မြန်ဆန် စိတ်ချရသော ဒစ်ဂျစ်တယ်ဆိုင်",
    "currency_suffix": "ကျပ်",
    "unlimited": "အကန့်အသတ်မရှိ",
    "days_unit": "{n} ရက်",
    "devices_unit": "စက် {n} လုံး",
    "back": "⬅️ နောက်သို့",
    "unknown_message": "နားမလည်ပါ။ အောက်ပါ မီနူးမှ ရွေးပေးပါ။",
    "rate_limited": "ခဏစောင့်ပြီးမှ ထပ်နှိပ်ပေးပါ။",
    "banned": "သင့်အကောင့်ကို ယာယီ ပိတ်ထားပါသည်။ အကူအညီအတွက် Support ကို ဆက်သွယ်ပါ။",
    "maintenance": "စနစ်ပြုပြင်နေပါသည်။ ခဏအကြာမှ ပြန်လာပေးပါ။",
    "panel_down": "⏳ ဆာဗာ ခဏ အလုပ်များနေပါသည်။ ခဏစောင့်ပေးပါ၊ ကျွန်ုပ်တို့ အလိုအလျောက် ပြန်ကြိုးစားပေးပါမည်။",
    "generic_error": "တစ်ခုခု မှားယွင်းသွားပါသည်။ ခဏအကြာမှ ထပ်ကြိုးစားပေးပါ။",
    # --- status ---
    "status_active": "အသုံးပြုနေဆဲ",
    "status_expired": "သက်တမ်းကုန်ပြီ",
    "status_none": "Key မရှိသေးပါ",
    "status_disabled": "ပိတ်ထားသည်",
    "kind_trial": "အခမဲ့ စမ်းသပ်",
    "kind_paid": "ငွေပေး Plan",
    # --- plan badges ---
    "badge_save": "{amount} သက်သာ",
    "badge_best": "အတန်ဆုံး",
    "plan_features": "Data အကန့်အသတ်မရှိ • စက် {devices} လုံး • {days} ရက်",
    # --- trial ---
    "trial_ok": "🎉 အခမဲ့ စမ်းသပ် Key ရပါပြီ။ {gb} GB၊ {days} ရက် သုံးနိုင်ပါသည်။",
    "trial_too_early": "⏳ အခမဲ့ စမ်းသပ်ကို နောက်ထပ် {remaining} အကြာတွင် ထပ်ယူနိုင်ပါမည်။",
    "trial_paid_active": "သင့်တွင် ငွေပေး Plan အသုံးပြုနေဆဲ ဖြစ်သောကြောင့် အခမဲ့ စမ်းသပ် မလိုတော့ပါ။ 😊",
    # --- orders / payment ---
    "order_open_exists": "သင့်တွင် မပြီးသေးသော အော်ဒါ {code} ရှိနေပါသည်။ ၎င်းကို အရင် ပြီးအောင် လုပ်ပေးပါ (သို့) ပယ်ဖျက်ပါ။",
    "order_not_found": "အော်ဒါ ရှာမတွေ့ပါ။",
    "order_bad_state": "ဤအော်ဒါကို ယခု ပြင်ဆင်၍ မရတော့ပါ။",
    "order_duplicate_screenshot": "ဤ Screenshot ကို အခြားအော်ဒါတွင် အသုံးပြုပြီးသား ဖြစ်ပါသည်။ ငွေလွှဲပြေစာ အသစ်ကို ပို့ပေးပါ။",
    "order_expired": "အော်ဒါ {code} သည် ၂၄ နာရီ ကျော်သွားသောကြောင့် ပယ်ဖျက်လိုက်ပါပြီ။ လိုအပ်ပါက အသစ်ပြန်မှာပါ။",
    "order_approved": "✅ ငွေပေးချေမှု အတည်ပြုပြီးပါပြီ။ ကျေးဇူးတင်ပါသည်။",
    "order_rejected": "❌ ငွေပေးချေမှုကို အတည်မပြုနိုင်ပါ။",
    "order_rejected_reason": "❌ ငွေပေးချေမှုကို အတည်မပြုနိုင်ပါ။\nအကြောင်းရင်း: {reason}",
    # --- key ---
    "regen_too_early": "Key အသစ်ကို ၂၄ နာရီ တစ်ကြိမ်သာ ပြောင်းနိုင်ပါသည်။ {remaining} အကြာမှ ထပ်ကြိုးစားပါ။",
    "regen_not_allowed": "Key ပြောင်းခြင်းကို ငွေပေး Plan အသုံးပြုသူများသာ လုပ်နိုင်ပါသည်။",
    "regen_ok": "🔑 Key အသစ် ထုတ်ပေးပြီးပါပြီ။ App ထဲတွင် Key အဟောင်းကို ဖျက်ပြီး အသစ်ကို ထည့်ပါ။",
    "no_key": "သင့်တွင် Key မရှိသေးပါ။ အခမဲ့ စမ်းသပ် (သို့) Plan ဝယ်ယူပါ။",
}


def t(key: str, **kwargs: object) -> str:
    """Look up a string; missing keys raise loudly in tests rather than showing English."""
    text = S[key]
    return text.format(**kwargs) if kwargs else text
