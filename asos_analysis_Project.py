import pandas as pd, numpy as np, re
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, seaborn as sns

raw = pd.read_csv('products_asos.csv', on_bad_lines='skip')
n_raw = len(raw)
df = raw.dropna(subset=['name','size','price','description']).copy()
print('raw rows read', n_raw, '| after dropping empty rows', len(df))

# --- ORIGINAL approach (what the notebook does) ---
orig = df.copy()
orig['price_n'] = pd.to_numeric(orig['price'], errors='coerce')
print('ORIGINAL: rows kept', orig.price_n.notna().sum(), 'dropped', orig.price_n.isna().sum())

# --- FIXED price: pull the number out of "Now  22.50" / "From 20.00"
df['price_n'] = df['price'].astype(str).str.extract(r'(\d+\.?\d*)')[0].astype(float)
df['on_sale'] = df['price'].astype(str).str.startswith('Now')
print('parsed prices', df.price_n.notna().sum(), '| on sale share', round(df.on_sale.mean(),3))

# --- drop duplicate listings
before=len(df); df = df.drop_duplicates(subset=['url']); print('dupes removed', before-len(df), '->', len(df))

# --- brand: text after "by " matched against start of product name
def brand(row):
    d, name = row['description'], row['name']
    if 'by ' not in d: return None
    after = d.split('by ',1)[1]
    k = 0
    while k < min(len(after), len(name)) and after[k]==name[k]: k+=1
    pre = name[:k]
    if k < len(name) and name[k] != ' ':
        pre = pre.rsplit(' ',1)[0] if ' ' in pre else ''
    return pre.strip() or None
df['Brand'] = df.apply(brand, axis=1)
print('brand not found', df.Brand.isna().sum())
print(df.Brand.value_counts().head(25))

# --- stockouts
sizes = df['size'].astype(str).str.split(',')
df['n_sizes'] = sizes.str.len()
df['oos'] = df['size'].astype(str).str.count('Out of stock')
df['oos_rate'] = df.oos/df.n_sizes
df['est_lost'] = df.price_n*df.oos
print('\nOverall: products', len(df), '| with >=1 size OOS', round((df.oos>0).mean()*100,1),'% | avg oos rate', round(df.oos_rate.mean()*100,1),'% | fully OOS', round((df.oos_rate==1).mean()*100,2),'%')
print('sale vs full price OOS rate:\n', df.groupby('on_sale').agg(n=('oos','size'),oos_rate=('oos_rate','mean'),any_oos=('oos',lambda s:(s>0).mean()),price=('price_n','mean')).round(3))

# top products
print(df.sort_values('est_lost',ascending=False).head(5)[['Brand','name','price_n','oos','n_sizes','est_lost']])

# brand table
d2 = df.dropna(subset=['Brand'])
g = d2.groupby('Brand').agg(products=('name','count'),avg_price=('price_n','mean'),oos_rate=('oos_rate','mean'),est_lost=('est_lost','sum')).reset_index()
g['lost_per_product']=g.est_lost/g.products
g = g[g.products>=30].sort_values('oos_rate',ascending=False)
print('\nBrands with >=30 products:', len(g))
print(g.round(2).head(12).to_string())
print(g.round(2).tail(8).to_string())
print('\nby lost revenue total'); print(g.sort_values('est_lost',ascending=False).round(0).head(8).to_string())
print('corr price vs oos_rate across brands', round(g.avg_price.corr(g.oos_rate),3))
print('median price', g.avg_price.median(), 'median oos', g.oos_rate.median())
g.to_csv('brand_summary.csv', index=False)

# chart
fig, ax = plt.subplots(figsize=(12,8))
sc = ax.scatter(g.avg_price, g.oos_rate, s=g.est_lost/g.est_lost.max()*900+40, alpha=.6, c=g.avg_price, cmap='viridis')
pm, om = g.avg_price.median(), g.oos_rate.median()
ax.axvline(pm,color='red',ls='--'); ax.axhline(om,color='red',ls='--')
for _,r in g[(g.avg_price>pm)&(g.oos_rate>om)].iterrows(): ax.annotate(r.Brand,(r.avg_price,r.oos_rate),xytext=(5,5),textcoords='offset points',fontsize=9)
ax.set_title('Brand strategy: price vs stockout rate (brands with 30+ products; bubble = est. lost revenue)')
ax.set_xlabel('Average price (£)'); ax.set_ylabel('Average share of sizes out of stock')
plt.tight_layout(); plt.savefig('brand_strategy.png',dpi=150)
