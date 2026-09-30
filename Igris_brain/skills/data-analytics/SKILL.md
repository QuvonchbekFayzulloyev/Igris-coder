---
name: data-analytics
description: >-
  Comprehensive data analysis skill covering pandas, matplotlib, plotly,
  statistical analysis, and ETL pipelines. USE WHEN: user asks for data
  analysis, visualization, statistical testing, CSV/JSON processing,
  dashboard creation, or data cleaning. Trigger on 'tahlil qil',
  'data analysis', 'grafik chiz', 'plot', 'visualize', 'statistik',
  'pandas', 'matplotlib', 'csv', 'excel', 'jadval'.
---

# Data Analytics Skill

## When to Use

- Data analysis and transformation
- Visualization (static and interactive)
- Statistical testing
- CSV/JSON/Excel processing
- Dashboard creation
- ETL pipeline design

## Core Stack

| Tool | Use Case |
|------|----------|
| `pandas` | Data manipulation, transformation |
| `matplotlib` | Static plots |
| `plotly` | Interactive visualizations |
| `scipy` | Statistical tests |
| `sklearn` | Machine learning basics |
| `openpyxl` | Excel read/write |

## Workflow

### 1. Load & Inspect
```python
import pandas as pd
df = pd.read_csv('data.csv')
print(df.shape, df.dtypes, df.describe())
```

### 2. Clean
```python
df.dropna(subset=['critical_col'], inplace=True)
df['date'] = pd.to_datetime(df['date'])
df['category'] = df['category'].astype('category')
```

### 3. Transform
```python
# Group and aggregate
summary = df.groupby('category').agg({
    'value': ['mean', 'std', 'count'],
    'date': ['min', 'max']
})

# Pivot
pivot = df.pivot_table(values='value', index='date', columns='category', aggfunc='sum')
```

### 4. Visualize
```python
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
df.groupby('date')['value'].sum().plot(ax=axes[0], title='Daily Total')
df.boxplot(column='value', by='category', ax=axes[1])
plt.tight_layout()
plt.savefig('analysis.png')
```

### 5. Report
```python
report = {
    'total_records': len(df),
    'date_range': f"{df['date'].min()} to {df['date'].max()}",
    'categories': df['category'].nunique(),
    'summary': summary.to_dict()
}
```

## Common Patterns

| Task | Code |
|------|------|
| Read CSV | `pd.read_csv('file.csv')` |
| Read Excel | `pd.read_excel('file.xlsx')` |
| Filter rows | `df[df['col'] > value]` |
| Add column | `df['new'] = df['a'] + df['b']` |
| Group by | `df.groupby('col').agg(...)` |
| Merge | `pd.merge(df1, df2, on='key')` |
| Pivot | `df.pivot_table(values, index, columns)` |
| Sort | `df.sort_values('col', ascending=False)` |
| Export | `df.to_csv('out.csv', index=False)` |
