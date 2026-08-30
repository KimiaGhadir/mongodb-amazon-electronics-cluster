# پنج Query مورد نیاز

1. **Q1 شناسه:** `parent_asin` و خروجی یک سند.
2. **Q2 pagination:** مرتب‌سازی پایدار بر `parent_asin` و `skip/limit`.
3. **Q3 category:** جستجوی مقدار در هر سطح آرایه `categories`.
4. **Q4 ویژگی فنی:** `$elemMatch` روی جفت دقیق `details.k` و `details.v`.
5. **Q5 ترکیبی:** `$and` برای وجود همزمان چند ویژگی و `$or` برای وجود حداقل یکی.

نمونه Q4:
```javascript
db.products.find({details: {$elemMatch: {k: "Resolution", v: "4K"}}})
```

نمونه Q5-AND:
```javascript
db.products.find({$and: [
  {details: {$elemMatch: {k: "RAM", v: "16GB"}}},
  {details: {$elemMatch: {k: "Storage", v: "512GB"}}}
]})
```
