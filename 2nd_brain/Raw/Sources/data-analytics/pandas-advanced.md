---
Title: "Data Analytics Toolkit"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-09-13
Processed: true
tags: ["source", "data-analytics"]
---

# Data Analytics Toolkit

## pandas Advanced Operations

### DataFrame Operations
```python
import pandas as pd
import numpy as np

# Multi-index
df = pd.DataFrame({
    'date': pd.date_range('2026-01-01', periods=100),
    'category': np.random.choice(['A', 'B', 'C'], 100),
    'value': np.random.randn(100)
})
df.set_index(['date', 'category'], inplace=True)

# Rolling statistics
df['rolling_mean'] = df['value'].rolling(window=7).mean()
df['rolling_std'] = df['value'].rolling(window=7).std()

# Window functions
df['pct_change'] = df['value'].pct_change()
df['cumsum'] = df['value'].cumsum()
```

### GroupBy Advanced
```python
# Custom aggregation
result = df.groupby('category').agg({
    'value': ['mean', 'std', lambda x: x.quantile(0.95)]
})

# Transform (preserves index)
df['z_score'] = df.groupby('category')['value'].transform(
    lambda x: (x - x.mean()) / x.std()
)

# Filter
df_filtered = df.groupby('category').filter(
    lambda x: len(x) > 10
)
```

## Visualization

### matplotlib
```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# Line plot
axes[0, 0].plot(df.index.get_level_values(0), df['value'])
axes[0, 0].set_title('Time Series')

# Histogram
axes[0, 1].hist(df['value'], bins=30, alpha=0.7)
axes[0, 1].set_title('Distribution')

# Scatter
axes[1, 0].scatter(df['value'], df['rolling_mean'], alpha=0.5)
axes[1, 0].set_title('Value vs Rolling Mean')

# Box plot
df.boxplot(column='value', by='category', ax=axes[1, 1])
axes[1, 1].set_title('By Category')

plt.tight_layout()
plt.savefig('analysis.png', dpi=150)
```

### plotly (interactive)
```python
import plotly.express as px
import plotly.graph_objects as go

fig = px.scatter(df.reset_index(), x='value', y='rolling_mean',
                 color='category', hover_data=['date'])
fig.write_html('interactive.html')
```

## Statistical Analysis

### Hypothesis Testing
```python
from scipy import stats

# T-test
group_a = df[df['category'] == 'A']['value']
group_b = df[df['category'] == 'B']['value']
t_stat, p_value = stats.ttest_ind(group_a, group_b)

# Chi-square
contingency = pd.crosstab(df['category'], df['value'] > 0)
chi2, p_value, dof, expected = stats.chi2_contingency(contingency)
```

### Regression
```python
from sklearn.linear_model import LinearRegression

X = df[['value']].values
y = df['rolling_mean'].values
model = LinearRegression().fit(X, y)
r_squared = model.score(X, y)
```

## SQL Optimization for Analytics

### Window Functions
```sql
-- Running total
SELECT date, value,
    SUM(value) OVER (ORDER BY date) as running_total,
    AVG(value) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as ma7
FROM sales;

-- Lag/Lead
SELECT date, value,
    LAG(value, 1) OVER (ORDER BY date) as prev_day,
    LEAD(value, 1) OVER (ORDER BY date) as next_day
FROM sales;
```

## ETL Pipeline Design

```
Extract → Validate → Transform → Load → Verify
   │          │           │         │        │
   ▼          ▼           ▼         ▼        ▼
 Source    Schema      Clean     Target    Check
 (API,     Check      (fill     (DB,      (counts,
  File,    (Pydantic)  nulls,   File)     types,
  DB)                  cast)              nulls)
```
