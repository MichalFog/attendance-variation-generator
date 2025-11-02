# מערכת עיבוד דוחות נוכחות – PDF

מערכת לעיבוד דוחות נוכחות מקובצי PDF, עם תמיכה בעברית ו-Docker.

## התקנה והרצה

### שיטה 1: הרצה עם Docker (מומלץ) 🐳

השיטה הקלה ביותר - עובדת על כל מערכת הפעלה ללא צורך בהתקנות נוספות.

#### דרישות:
- [Docker](https://www.docker.com/get-started) מותקן על המחשב
- [Docker Compose](https://docs.docker.com/compose/install/) (מגיע עם Docker Desktop)

#### הוראות הרצה:

1. **עיבוד כל הקבצים בתיקיית `input_reports`:**
   ```bash
   docker-compose up
   ```

2. **עיבוד קובץ בודד:**
   ```bash
   docker-compose run --rm attendance-processor python main.py sample_type_A.pdf
   ```

3. **הרצה ידנית (המומלץ - עובד טוב ב-PowerShell):**
   ```powershell
   docker run --rm -v "${PWD}/input_reports:/app/input_reports" -v "${PWD}/output_reports:/app/output_reports" attendance-variation
   ```
   
   **לתקופת פיתוח/בדיקה** (אם צריך לבנות מחדש):
   ```powershell
   docker build -t attendance-variation .
   docker run --rm -v "${PWD}/input_reports:/app/input_reports" -v "${PWD}/output_reports:/app/output_reports" attendance-variation
   ```

הקבצים המעובדים ייכתבו לתיקייה `output_reports` בשם `<שם_קובץ>_variation.pdf`.

---

### שיטה 2: התקנה מקומית (לפיתוח)

#### דרישות:
- Python 3.10 או גרסה חדשה יותר
- Tesseract OCR עם תמיכה בעברית
  - **Windows**: הורד והתקן מ-[GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
    - וודא שהשפה העברית (heb) נבחרה בהתקנה
  - **macOS**: `brew install tesseract tesseract-lang`
  - **Linux (Debian/Ubuntu)**: `sudo apt-get install tesseract-ocr tesseract-ocr-heb`

#### הוראות התקנה:

1. התקן את החבילות הנדרשות:
   ```bash
   pip install -r requirements.txt
   ```

2. הרץ את המערכת:
   ```bash
   # עיבוד כל הקבצים
   python main.py
   
   # עיבוד קובץ בודד
   python main.py sample_type_A.pdf
   ```

הקבצים המעובדים ייכתבו לתיקייה `output_reports` בשם `<שם_קובץ>_variation.pdf`.

---

## מה המערכת עושה?

1. **קריאת PDF**: קוראת את קובץ ה-PDF המקורי (טקסט מקורי קודם, ואם צריך - OCR)
2. **חילוץ נתונים**: מחלצת טבלת נוכחות עם תאריכים, זמנים ושעות
3. **אימות ותיקונים**: מיישמת כללי אימות מינימליים ותיקונים דטרמיניסטיים
   - שומרת על נתונים תקינים
   - מתקנת רק שורות בעייתיות
4. **זיהוי סוג דוח**: מזהה אוטומטית את סוג הדוח (A או B)
   - **סוג A**: רשימת תאריכים ארוכה עם בלוקים של זמנים חוזרים
   - **סוג B**: פורמט אחר
5. **יצירת PDF חדש**: יוצרת PDF חדש עם הנתונים המעובדים
   - עמודות לפי סוג הדוח:
     - **סוג A**: תאריך, יום בשבוע, שעת כניסה, שעת יציאה, סה"כ שעות, הפסקה, שבת
     - **סוג B**: תאריך, יום בשבוע, שעת כניסה, שעת יציאה, סה"כ שעות

## מבנה הפרויקט

```
├── main.py            # ניהול תהליך העיבוד (קריאה → חילוץ → כללים → כתיבה)
├── report_utils.py    # AttendancePDFReader (PDF/OCR), AttendanceTableExtractor (פרסור)
├── rules.py           # AttendanceVariationRules (תיקונים מינימליים, יום בשבוע/שבת)
├── report_writer.py   # AttendancePDFWriter (עימוד, עמודות דינמיות, סיכומים)
├── Dockerfile         # הגדרת תמונת Docker
├── docker-compose.yml # הגדרת Docker Compose
├── requirements.txt   # תלויות Python
├── input_reports/     # קבצי PDF מקוריים
└── output_reports/    # קבצי PDF מעובדים
```

## פתרון בעיות

### בעיות ב-Docker

- **הבילד נכשל**: ודא ש-Docker רץ ויש חיבור לאינטרנט להורדת התלויות
- **הרשאות על volumes**: ב-Linux/Mac, ודא שהתיקיות `input_reports` ו-`output_reports` ניתנות לכתיבה
- **אין קבצי פלט**: ודא שתיקיית `output_reports` קיימת וניתנת לכתיבה

### בעיות בהתקנה מקומית

- **Tesseract לא נמצא**: הקוד משתמש ב-Tesseract מה-PATH אוטומטית. אם הוא מותקן במקום אחר, הגדר את המשתנה `TESSERACT_CMD` לנתיב המלא
- **תווים עבריים לא מופיעים**: הקוד מחפש אוטומטית פונטים שתומכים בעברית (DejaVu Sans, Liberation Sans, או Arial)

## הערות טכניות

- המערכת משתמשת ב-OCR רק אם הטקסט המקורי ב-PDF לא מספיק
- תמיכה מלאה בעברית ואנגלית
- הקוד מותאם לעבודה ב-Docker ובסביבות לוקאליות
