# מערכת עיבוד דוחות נוכחות – יצירת וריאציה אמינה

## התקנה מהירה

```bash
pip install -r requirements.txt
```

חשוב: יש להתקין Tesseract OCR ולהגדיר עברית.
- Windows: התקן מ־`https://github.com/UB-Mannheim/tesseract/wiki`
- Linux: `sudo apt-get install tesseract-ocr tesseract-ocr-heb`
- macOS: `brew install tesseract tesseract-lang`

ב־Windows ודא שהנתיב נכון בקובץ `report_utils.py` (ברירת מחדל: `C:\Program Files\Tesseract-OCR\tesseract.exe`).

## שימוש

```bash
python main.py                 # יעבד את כל הקבצים בתיקיית input_reports
python main.py sample_type_A.pdf   # קובץ יחיד
```

הקבצים המעובדים יישמרו בתיקייה `output_reports` עם סיומת `_variation.pdf`.

## מה המערכת עושה
- זיהוי סוג הדו"ח בעזרת OCR של העמוד הראשון לפי הופעת "שבת" (Type A אם מופיע, אחרת Type B).
- חילוץ טבלה מכל העמודים עם עמודות: `date`, `start`, `end`, `hours`.
- החלת חוקים דטרמיניסטיים שמייצרים וריאציה אמינה:
  - הזזות דקות קטנות לפי סוג הדו"ח והיום (ללא אקראיות).
  - הבטחת `end > start` (עם טיפול בלילה).
  - תחימת שעות יומיות לטווח סביר [4.0, 12.0].
- יצירת PDF חדש עם מבנה תואם לפי סוג הדו"ח:
  - Type A: עמודות תאריך/כניסה/יציאה/שעות/שבת.
  - Type B: עמודות תאריך/כניסה/יציאה/שעות.
  - כותרת, טבלה ממוסדרת וסיכומי שעות וימי עבודה.

## מבנה הקבצים

```
├── main.py           # הרצה, זיהוי סוג, ייצור PDF
├── report_utils.py   # OCR, חילוץ טבלה, רישום פונט עברי
├── rules.py          # החוקים ליצירת וריאציה
├── input_reports/    # קבצי PDF מקור
└── output_reports/   # קבצי PDF תוצר
```

## תקלות נפוצות
- Tesseract לא נמצא: עדכן את הנתיב ב־`report_utils.py` או התקן עברית.
- עברית לא מוצגת: המערכת מנסה לרשום פונט `DejaVuSans`/`Arial`. אם לא נמצא, נעשה שימוש ב־Helvetica שעשוי לא לתמוך בעברית.

## דוגמת הרצה

```bash
python main.py
```

התוצר יופיע כ־`output_reports/<name>_variation.pdf`.
