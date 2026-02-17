# MLZ Community

إضافة Millennium لتحميل الألعاب بسهولة على Steam.

## التثبيت

1. حمّل آخر إصدار من [Releases](../../releases)
2. فك الضغط في مجلد `plugins` في Millennium
3. أعد تشغيل Steam

## الاستخدام

1. افتح صفحة أي لعبة في Steam
2. اضغط على زر "إضافة عبر MLZ Community"
3. انتظر حتى يكتمل التحميل
4. أعد تشغيل Steam

## للمطورين - إنشاء إصدار جديد

### الطريقة السريعة:
```
scripts\quick-release.bat
```

### الطريقة اليدوية:
```powershell
.\scripts\release.ps1 -Version "1.0.1" -Message "وصف التحديث"
```

ثم:
1. نفذ أوامر Git المعروضة
2. اذهب لـ GitHub → Releases → Create new release
3. اختر التاج وارفق ملف ZIP
4. انشر الإصدار

## الهيكل

```
MLZCommunity/
├── plugin.json          # إعدادات البلقن
├── requirements.txt     # المتطلبات
├── backend/             # الكود الخلفي (Python)
├── locales/             # ملفات الترجمة
├── .millennium/Dist/    # الكود الأمامي (JS)
└── scripts/             # سكربتات المساعدة
```

## الترخيص

MIT License
