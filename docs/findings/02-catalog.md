# 02 · Catalogue

Queries: `eda/02-catalog.py`, `eda/08-product-appeal.py`. Local copy: `data/catalog.json`.

## Shape

| | |
|---|---|
| Products | 5,000, all active at the start |
| Categories | 10 (322 to 640 products each) |
| Subcategories | 89, each inside one category, 1 to ~100 products |
| Brands | 80, exactly 8 per category |
| Price | all end in .99; quantiles 5/25/50/75/95 = 7, 17, 31, 54, 144 € |
| Description | 4 sentence templates, filled with brand, subcategory and **2 of 20 feature phrases** |

Example: `Vedo Yoga Mats with organic ingredients and extra durability.`

The description holds no information beyond brand, subcategory and the two phrases. No embedding is needed: parse the two phrases.

## What a product's attributes say about its appeal

Organic history, one row per product. Buy per view spreads widely: quantiles 5/50/95 = 0.11%, 1.66%, 11.36%.

| Attribute | Best | Worst |
|---|---|---|
| Feature phrase | great value for money 10.6%, minimalist design 8.0% | organic ingredients 2.3%, travel-ready build 2.8% |
| Category | Books & Media 8.5%, Toys & Baby 6.2% | Home & Garden 2.3%, Pets 3.0% |
| Subcategory | E-Readers 12.7%, Jeans 9.8% | Shaver Blades 0.8%, Lamps 0.9% |
| Brand | Penisa 11.6%, Rekozo 9.6% | Zopeno 1.0%, Galure 1.5% |

Share of variance across products explained (in-sample R²):

| Attributes | log(views) | buy per view |
|---|---|---|
| Category | 0.12 | 0.11 |
| Subcategory | 0.27 | 0.20 |
| Brand | 0.25 | 0.14 |
| Feature phrases | 0.09 | 0.18 |
| Price | 0.00 | 0.03 |
| Subcategory + brand + phrases + price | **0.50** | **0.43** |

## Takeaways

- **A product never seen before can be scored from subcategory, brand and its two phrases.** About half of what makes a product popular is in those attributes. This is the cold-start branch for new products.
- The other half is product-specific and must be learned from live views.
- Price alone explains almost nothing across products. Cheap products convert a little better (correlation −0.16).
- Product age does not matter: the newest 250 products get the same views as the rest.
