"""ALL customer-facing text (Burmese, Myanmar Unicode — never Zawgyi).

Edit the text freely; keep the {placeholders} intact. Use t("key", name=value).
Consistent emoji palette per spec §9.5: ✨ 🔑 📶 🛡️ 💳 ⏳
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
    "cancel": "✖️ ပယ်ဖျက်မည်",
    "unknown_message": "နားမလည်ပါ။ အောက်ပါ မီနူးမှ ရွေးပေးပါ။",
    "rate_limited": "⏳ ခဏစောင့်ပြီးမှ ထပ်နှိပ်ပေးပါ။",
    "banned": "🛡️ သင့်အကောင့်ကို ယာယီ ပိတ်ထားပါသည်။ အကူအညီအတွက် Support ကို ဆက်သွယ်ပါ။",
    "maintenance": "⏳ စနစ်ပြုပြင်နေပါသည်။ ခဏအကြာမှ ပြန်လာပေးပါ။",
    "panel_down": "⏳ ဆာဗာ ခဏ အလုပ်များနေပါသည်။ ခဏစောင့်ပေးပါ၊ ကျွန်ုပ်တို့ အလိုအလျောက် ပြန်ကြိုးစားပေးပါမည်။",
    "generic_error": "တစ်ခုခု မှားယွင်းသွားပါသည်။ ခဏအကြာမှ ထပ်ကြိုးစားပေးပါ။",
    # --- main menu & commands ---
    "welcome_body": (
        "🛡️ <b>လုံခြုံ မြန်ဆန် စိတ်ချရသော ဒစ်ဂျစ်တယ်ဆိုင်</b>\n\n"
        "မြန်နှုန်းမြင့် Shadowsocks VPN Key များကို အလိုအလျောက် ဝယ်ယူပြီး ချက်ချင်း အသုံးပြုနိုင်ပါသည်။\n"
        "အောက်ပါ ခလုတ်များမှ လိုအပ်ရာကို ရွေးချယ်ပါ။"
    ),
    "help_body": (
        "🛡️ <b>အသုံးပြုပုံ အကျဉ်းချုပ်</b>\n\n"
        "• <b>အခမဲ့ စမ်းသပ်</b> — 5 GB (7 ရက်) အခမဲ့ ရယူနိုင်ပါသည်။\n"
        "• <b>Plan ဝယ်မည်</b> — KBZ Pay ဖြင့် ငွေလွှဲပြီး Screenshot ပို့ရုံဖြင့် ဝယ်ယူနိုင်ပါသည်။\n"
        "• <b>ကျွန်ုပ်၏ Key</b> — Key Link နှင့် QR Code ကို ကြည့်ရှုနိုင်ပါသည်။\n"
        "• <b>သုံးစွဲမှု</b> — လက်ကျန် Data နှင့် သက်တမ်းကို စစ်ဆေးနိုင်ပါသည်။\n"
        "• <b>ထည့်သွင်းနည်း</b> — ဖုန်းနှင့် ကွန်ပျူတာအတွက် အဆင့်ဆင့် လမ်းညွှန်။\n\n"
        "Commands: /start • /myid • /help"
    ),
    "myid_body": "🔑 သင့် Telegram ID: <code>{user_id}</code>",
    "btn_open_app": "✨ Mini App ဖွင့်မည်",
    "btn_trial": "⏳ အခမဲ့ စမ်းသပ် (5 GB)",
    "btn_buy": "💳 Plan ဝယ်မည်",
    "btn_my_key": "🔑 ကျွန်ုပ်၏ Key",
    "btn_usage": "📶 သုံးစွဲမှု စစ်မည်",
    "btn_guide": "🛡️ ထည့်သွင်းနည်း လမ်းညွှန်",
    "btn_support": "💬 Support ဆက်သွယ်ရန်",
    "btn_regen_key": "🔑 Key အသစ်လဲမည်",
    # --- status ---
    "status_active": "အသုံးပြုနေဆဲ",
    "status_expired": "သက်တမ်းကုန်ပြီ",
    "status_none": "Key မရှိသေးပါ",
    "status_disabled": "ပိတ်ထားသည်",
    "kind_trial": "အခမဲ့ စမ်းသပ်",
    "kind_paid": "ငွေပေး Plan",
    # --- plan badges & cards ---
    "badge_save": "{amount} သက်သာ",
    "badge_best": "အတန်ဆုံး",
    "plan_features": "Data အကန့်အသတ်မရှိ • စက် {devices} လုံး • {days} ရက်",
    "plans_header": "💳 <b>VPN Plan များ ရွေးချယ်ပါ</b>\nData အကန့်အသတ်မရှိ • စက် 1 လုံး • မြန်နှုန်းမြင့်",
    "plan_card_line": (
        "• <b>{name}</b> ({days} ရက်) — {price_part}{badge_part}"
    ),
    "btn_select_plan": "💳 {name} — {price}",
    # --- trial ---
    "trial_ok": "🔑 အခမဲ့ စမ်းသပ် Key ရပါပြီ။ <b>{gb} GB</b>၊ <b>{days} ရက်</b> သုံးနိုင်ပါသည်။",
    "trial_too_early": "⏳ အခမဲ့ စမ်းသပ်ကို နောက်ထပ် <b>{remaining}</b> အကြာတွင် ထပ်ယူနိုင်ပါမည်။",
    "trial_paid_active": "🛡️ သင့်တွင် ငွေပေး Plan အသုံးပြုနေဆဲ ဖြစ်သောကြောင့် အခမဲ့ စမ်းသပ် မလိုတော့ပါ။",
    # --- orders / payment ---
    "order_created": (
        "💳 <b>အော်ဒါအသစ် — {plan_name} ({days} ရက်)</b>\n\n"
        "• အော်ဒါကုဒ်: <code>{code}</code>\n"
        "• ပေးချေရမည့်ငွေ: <b>{amount}</b>\n"
        "• ငွေလွှဲရန်: <b>KBZ Pay</b>\n"
        "• ဖုန်းနံပါတ်: <code>{kbz_number}</code>\n"
        "• အကောင့်အမည်: <b>{kbz_name}</b>\n\n"
        "📌 <b>လုပ်ဆောင်ရန် အဆင့်များ</b>\n"
        "1. အထက်ပါ KBZ Pay နံပါတ်သို့ <b>{amount}</b> အတိအကျ လွှဲပေးပါ။\n"
        "2. မှတ်ချက် (Note) တွင် <code>{code}</code> ဟု ထည့်ပေးပါ။\n"
        "3. ငွေလွှဲပြေစာ <b>Screenshot ပုံကို ဤ Chat သို့ တိုက်ရိုက် ပို့ပေးပါ။</b>"
    ),
    "order_send_photo_prompt": "⏳ ကျေးဇူးပြု၍ အော်ဒါ <code>{code}</code> အတွက် ငွေလွှဲ Screenshot ပုံ (Photo) ကို ပို့ပေးပါ။",
    "order_received_wait": (
        "⏳ <b>Screenshot လက်ခံရရှိပါပြီ။</b>\n"
        "အော်ဒါကုဒ်: <code>{code}</code>\n"
        "စစ်ဆေးပြီးသည်နှင့် သင့် Key ကို အလိုအလျောက် ပို့ပေးပါမည်။"
    ),
    "order_instant_key_intro": (
        "✨ <b>အော်ဒါ <code>{code}</code> ({plan_name}) လက်ခံရရှိပါပြီ။</b>"
    ),
    "order_key_extended": (
        "✨ <b>အော်ဒါ <code>{code}</code> ({plan_name}) လက်ခံရရှိပါပြီ။</b>\n"
        "• လက်ရှိ Key တွင် <b>+{days} ရက်</b> နှင့် <b>Unlimited Data</b> တိုးပေးထားပါသည်။\n"
        "• သက်တမ်းကုန်ရက်: <b>{expiry_date}</b> (<b>{days_left} ရက်</b> ကျန်)\n"
        "• Key အသစ် ထပ်ထည့်ရန် မလိုဘဲ လက်ရှိ Key အတိုင်း ဆက်သုံးနိုင်ပါသည်။"
    ),
    "order_cancelled": "အော်ဒါ <code>{code}</code> ကို ပယ်ဖျက်ပြီးပါပြီ။",
    "order_open_exists": "⏳ သင့်တွင် မပြီးသေးသော အော်ဒါ <code>{code}</code> ရှိနေပါသည်။ ၎င်းကို အရင် ပြီးအောင် လုပ်ပေးပါ (သို့) ပယ်ဖျက်ပါ။",
    "order_not_found": "အော်ဒါ ရှာမတွေ့ပါ။",
    "order_bad_state": "ဤအော်ဒါကို ယခု ပြင်ဆင်၍ မရတော့ပါ။",
    "order_duplicate_screenshot": "💳 ဤ Screenshot ကို အခြားအော်ဒါတွင် အသုံးပြုပြီးသား ဖြစ်ပါသည်။ ငွေလွှဲပြေစာ အသစ်ကို ပို့ပေးပါ။",
    "order_expired": "⏳ အော်ဒါ <code>{code}</code> သည် 24 နာရီ ကျော်သွားသောကြောင့် ပယ်ဖျက်လိုက်ပါပြီ။ လိုအပ်ပါက အသစ်ပြန်မှာပါ။",
    "order_approved": "✨ ငွေပေးချေမှု အတည်ပြုပြီးပါပြီ။ ကျေးဇူးတင်ပါသည်။",
    "order_approved_card": (
        "<b>✨ ငွေပေးချေမှု အတည်ပြုပြီးပါပြီ။ ကျေးဇူးတင်ပါသည်။</b>\n"
        "• Plan: <b>{plan_name}</b> (+{days} ရက် • Unlimited Data)\n"
        "• သက်တမ်းကုန်ရက်: <b>{expiry_date}</b> (<b>{days_left} ရက်</b> ကျန်)\n"
        "• Key အသစ် ထပ်ထည့်ရန် မလိုဘဲ လက်ရှိ Key အတိုင်း ဆက်သုံးနိုင်ပါသည်။"
    ),
    "order_rejected": "❌ ငွေပေးချေမှုကို အတည်မပြုနိုင်ပါ။",
    "order_rejected_reason": "❌ ငွေပေးချေမှုကို အတည်မပြုနိုင်ပါ။\nအကြောင်းရင်း: <b>{reason}</b>",
    # --- key & usage ---
    "key_card": (
        "🔑 <b>သင့် VPN Key</b>\n"
        "• အမျိုးအစား: <b>{kind}</b> ({status})\n"
        "• သက်တမ်းကုန်ရက်: <b>{expiry_date}</b> (<b>{days_left} ရက်</b> ကျန်)\n"
        "📋 <b>Key Link (နှိပ်၍ ကူးယူပါ):</b>\n"
        "<code>{link}</code>"
    ),
    "usage_card_trial": (
        "📶 <b>Data သုံးစွဲမှု (အခမဲ့ စမ်းသပ်)</b>\n\n"
        "{bar} <b>{percent}%</b>\n"
        "• သုံးပြီး: <b>{used}</b> / <b>{quota}</b>\n"
        "• လက်ကျန် သက်တမ်း: <b>{days_left} ရက်</b> ({expiry_date})\n"
        "• အခြေအနေ: <b>{status}</b>"
    ),
    "usage_card_paid": (
        "📶 <b>Data သုံးစွဲမှု (ငွေပေး Plan)</b>\n\n"
        "• Data ပမာဏ: <b>အကန့်အသတ်မရှိ (Unlimited)</b>\n"
        "• လက်ရှိ သုံးပြီး: <b>{used}</b>\n"
        "• လက်ကျန် သက်တမ်း: <b>{days_left} ရက်</b> ({expiry_date})\n"
        "• အခြေအနေ: <b>{status}</b>"
    ),
    "regen_too_early": "⏳ Key အသစ်ကို 24 နာရီ တစ်ကြိမ်သာ ပြောင်းနိုင်ပါသည်။ <b>{remaining}</b> အကြာမှ ထပ်ကြိုးစားပါ။",
    "regen_not_allowed": "🔑 Key ပြောင်းခြင်းကို ငွေပေး Plan အသုံးပြုသူများသာ လုပ်နိုင်ပါသည်။",
    "regen_ok": "🔑 Key အသစ် ထုတ်ပေးပြီးပါပြီ။ App ထဲတွင် Key အဟောင်းကို ဖျက်ပြီး အသစ်ကို ထည့်ပါ။",
    "no_key": "🔑 သင့်တွင် Key မရှိသေးပါ။ အခမဲ့ စမ်းသပ် (သို့) Plan ဝယ်ယူပါ။",
    # --- setup guides ---
    "guide_menu": (
        "🛡️ <b>VPN ထည့်သွင်းနည်း လမ်းညွှန်</b>\n\n"
        "သင်အသုံးပြုသော စက်အမျိုးအစားကို ရွေးချယ်ပါ။"
    ),
    "btn_guide_android": "📱 Android",
    "btn_guide_ios": "🍎 iPhone / iPad (iOS)",
    "btn_guide_desktop": "💻 Windows / Mac",
    "guide_android": (
        "📱 <b>Android အတွက် ထည့်သွင်းနည်း</b>\n\n"
        "အကြံပြု App များ: <b>Outline</b>, <b>Hiddify</b>, <b>v2rayNG</b>, <b>Shadowsocks</b>\n\n"
        "1. Play Store မှ <b>Outline</b> (သို့) <b>v2rayNG</b> ကို ဒေါင်းလုဒ်ဆွဲပါ။\n"
        "2. Bot မှ <code>ss://...</code> Key Link ကို တစ်ချက်နှိပ်၍ Copy ကူးပါ။\n"
        "3. App ကိုဖွင့်ပြီး <b>'+' (Add Server)</b> ကိုနှိပ်ပါ — Clipboard မှ အလိုအလျောက် ဖတ်ပေးပါမည် (သို့) QR Code ကို Scan ဖတ်ပါ။\n"
        "4. <b>Connect</b> ကိုနှိပ်၍ အသုံးပြုနိုင်ပါပြီ။"
    ),
    "guide_ios": (
        "🍎 <b>iPhone / iPad (iOS) အတွက် ထည့်သွင်းနည်း</b>\n\n"
        "အကြံပြု App များ: <b>Outline</b>, <b>Streisand</b>, <b>Hiddify</b>\n\n"
        "1. App Store မှ <b>Outline</b> (သို့) <b>Streisand</b> ကို ထည့်သွင်းပါ။\n"
        "2. Bot မှ <code>ss://...</code> Key Link ကို Copy ကူးပါ။\n"
        "3. App ကိုဖွင့်ပြီး <b>'+'</b> နှိပ်၍ <b>Import from Clipboard</b> (သို့) <b>Scan QR</b> ကို ရွေးပါ။\n"
        "4. VPN Permission ကို <b>Allow</b> ပေးပြီး Connect လုပ်ပါ။"
    ),
    "guide_desktop": (
        "💻 <b>Windows / macOS အတွက် ထည့်သွင်းနည်း</b>\n\n"
        "အကြံပြု App များ: <b>Outline Client</b>, <b>Hiddify</b>\n\n"
        "1. <b>Outline Client</b> (သို့) <b>Hiddify</b> ကို ကွန်ပျူတာတွင် ထည့်သွင်းပါ။\n"
        "2. <code>ss://...</code> Key Link ကို Copy ကူးပါ။\n"
        "3. App ထဲတွင် <b>Add Server / '+'</b> ကိုနှိပ်ပြီး Key ကို Paste ထည့်ပါ။\n"
        "4. <b>Connect</b> နှိပ်၍ အသုံးပြုပါ။"
    ),
    # --- support ---
    "support_body": (
        "💬 <b>အကူအညီ လိုအပ်ပါသလား?</b>\n\n"
        "ငွေပေးချေမှု သို့မဟုတ် Key အသုံးပြုရာတွင် အခက်အခဲရှိပါက အောက်ပါခလုတ်မှတစ်ဆင့် Admin ထံ ဆက်သွယ်နိုင်ပါသည်။"
    ),
    "btn_contact_support": "💬 Support သို့ စာပို့ရန်",
    # --- automated notifications ---
    "notify_expiring_1d": (
        "⏳ <b>သက်တမ်းကုန်ဆုံးရန် 1 ရက်သာ လိုပါတော့သည်။</b>\n"
        "သင့် VPN Key သည် <b>{expiry_date}</b> တွင် သက်တမ်းကုန်ပါမည်။ အဆက်မပြတ် သုံးနိုင်ရန် Plan သက်တမ်းတိုးထားနိုင်ပါသည်။"
    ),
    "notify_expired": (
        "⏳ <b>သင့် VPN Key သက်တမ်းကုန်သွားပါပြီ။</b>\n"
        "ဆက်လက်အသုံးပြုလိုပါက Plan ဝယ်ယူ၍ ချက်ချင်း သက်တမ်းတိုးနိုင်ပါသည်။"
    ),
    "notify_quota_80": (
        "📶 <b>အခမဲ့ စမ်းသပ် Data 80% ပြည့်ပါပြီ။</b>\n"
        "သုံးပြီး: <b>{used}</b> / <b>{quota}</b>။ Data အကန့်အသတ်မရှိ သုံးလိုပါက ငွေပေး Plan သို့ အဆင့်မြှင့်နိုင်ပါသည်။"
    ),
    "notify_quota_100": (
        "📶 <b>အခမဲ့ စမ်းသပ် Data ကုန်သွားပါပြီ။</b>\n"
        "Data အကန့်အသတ်မရှိ ဆက်သုံးလိုပါက ငွေပေး Plan ဝယ်ယူနိုင်ပါသည်။"
    ),
    # --- admin (kept concise; admin also sees Burmese UI) ---
    "admin_menu": "🛡️ <b>Admin Panel</b>\nလုပ်ဆောင်လိုသည်ကို ရွေးပါ။",
    "btn_adm_pending": "💳 စစ်ဆေးရန် အော်ဒါများ ({n})",
    "btn_adm_stats": "📶 စာရင်းချုပ် (Stats)",
    "btn_adm_find": "🔑 သုံးစွဲသူ ရှာရန်",
    "btn_adm_broadcast": "✨ အားလုံးထံ စာပို့ရန်",
    "btn_adm_maint": "⏳ ပြုပြင်မှုစနစ်: {state}",
    "btn_adm_csv": "📋 အော်ဒါ CSV ထုတ်ရန်",
    "btn_approve": "✅ Paid (အတည်ပြုမည်)",
    "btn_reject": "❌ Unpaid (ငွေမရရှိပါ)",
    "btn_suspend_key": "⏸️ Key ယာယီပိတ်မည်",
    "btn_resume_key": "▶️ Key ပြန်ဖွင့်မည်",
    "btn_edit_key": "✏️ Key ပြင်မည်",
    "btn_msg_user": "✉️ စာပို့မည်",
    "btn_adm_web": "🌐 Web Admin ဖွင့်မည်",
    "btn_adm_panels": "🖧 3X-UI ဆာဗာများ ({n})",
    "btn_skip_reason": "အကြောင်းရင်း မထည့်ဘဲ ပယ်ချမည်",
    "adm_new_order_caption": (
        "💳 <b>ငွေလွှဲ Screenshot နှင့် Key အချက်အလက်</b>\n"
        "• အော်ဒါ: <code>{code}</code>\n"
        "• အကောင့် ID: <code>{user_id}</code> ({username})\n"
        "• Package: <b>{plan_name}</b> ({days} ရက်) — <b>{amount}</b>\n"
        "• Key: <code>{key_email}</code> ({key_status})\n"
        "• အခြေအနေ: <b>Key ကြိုတင်ထုတ်ပေးပြီး (စစ်ဆေးရန်)</b>"
    ),
    "adm_ask_reject_reason": "အော်ဒါ <code>{code}</code> ပယ်ချရသည့် အကြောင်းရင်းကို စာရိုက်ပို့ပါ (သို့) အောက်ပါခလုတ်ကို နှိပ်ပါ။",
    "adm_ask_msg_user": "သုံးစွဲသူ <code>{user_id}</code> ထံ ပို့လိုသော စာသားကို ရိုက်ပို့ပါ။",
    "adm_msg_from_admin": "🛡️ <b>Admin မှ အကြောင်းကြားစာ</b>\n\n{text}",
    "key_suspended_notify": "⏸️ သင့် VPN Key ကို Admin မှ ယာယီ ပိတ်ထားပါသည်။ အကူအညီလိုပါက Support သို့ ဆက်သွယ်ပါ။",
    "key_resumed_notify": "▶️ သင့် VPN Key ကို ပြန်လည် ဖွင့်ပေးလိုက်ပါပြီ။",
    "sub_link_section": "\n🌐 <b>All-in-One Subscription Link:</b>\n<code>{sub_url}</code>\n",
    "extra_servers_section": "\n🖧 <b>အပို ဆာဗာ Key များ:</b>\n{servers}",
    "adm_stats_body": (
        "📶 <b>Exabyte စာရင်းချုပ်</b>\n\n"
        "• စုစုပေါင်း သုံးစွဲသူ: <b>{total_users}</b>\n"
        "• ငွေပေး Plan (Active): <b>{active_paid}</b>\n"
        "• အခမဲ့ စမ်းသပ် (Active): <b>{active_trials}</b>\n"
        "• စစ်ဆေးရန် အော်ဒါ: <b>{pending_orders}</b>\n"
        "• ယနေ့ ဝင်ငွေ: <b>{today_revenue}</b>\n"
        "• ယခုလ ဝင်ငွေ: <b>{month_revenue}</b>"
    ),
    "adm_ask_find": "ရှာလိုသော Telegram ID (သို့) @username ကို ပို့ပေးပါ။",
    "adm_user_not_found": "သုံးစွဲသူ ရှာမတွေ့ပါ။",
    "adm_user_card": (
        "🔑 <b>သုံးစွဲသူ အချက်အလက်</b>\n"
        "• ID: <code>{user_id}</code> ({username})\n"
        "• Banned: <b>{banned}</b>\n"
        "• Key: <b>{key_summary}</b>\n"
        "• အော်ဒါအရေအတွက်: <b>{order_count}</b>"
    ),
    "adm_ask_broadcast": "သုံးစွဲသူ အားလုံးထံ ပို့လိုသော စာသားကို ရိုက်ပို့ပါ။",
    "adm_broadcast_preview": "✨ <b>ပို့မည့်စာ နမူနာ</b> ({count} ဦးထံ ပို့ပါမည်)\n\n{text}",
    "btn_adm_broadcast_confirm": "✅ အတည်ပြု ပို့မည်",
    "adm_broadcast_done": "✨ စာပို့ပြီးပါပြီ — အောင်မြင်: <b>{ok}</b>၊ မရောက်: <b>{failed}</b>",
    "adm_action_done": "✅ လုပ်ဆောင်ပြီးပါပြီ။",
    "adm_no_pending": "စစ်ဆေးရန် အော်ဒါ မရှိပါ။",
}


def t(key: str, **kwargs: object) -> str:
    """Look up a string; missing keys raise loudly in tests rather than showing English."""
    text = S[key]
    return text.format(**kwargs) if kwargs else text
