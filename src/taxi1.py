# -*- coding: utf-8 -*-
"""时间对齐深度诊断: 完整48槽曲线 + 凌晨低谷校准 + 三段对比"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
rcParams['axes.unicode_minus'] = False

data = np.load("C:/Users/ASUS/Downloads/TaxiBJ21.npy")          # 路径按需修改
SEG_BOUNDS, SEG_NAMES = [0, 1440, 2832, 4272], ['2012段', '2014段', '2015段']
hhmm = lambda s: '%02d:%02d' % (s // 2, 30 * (s % 2))

curves = {}
for k in range(3):
    seg = data[SEG_BOUNDS[k]:SEG_BOUNDS[k+1]]
    curves[SEG_NAMES[k]] = np.array([seg[s::48].mean() for s in range(48)])
curves['总体'] = np.array([data[s::48].mean() for s in range(48)])

tbl = pd.DataFrame({'槽': range(48), '时间': [hhmm(s) for s in range(48)]})
for nm in SEG_NAMES + ['总体']:
    tbl[nm] = curves[nm].round(4)
pd.set_option('display.max_rows', 50)
print(tbl.to_string(index=False))

for nm in SEG_NAMES + ['总体']:
    c = curves[nm]
    print('%s: 最低谷 槽%d(%s) | 最高峰 槽%d(%s)'
          % (nm, c.argmin(), hhmm(c.argmin()), c.argmax(), hhmm(c.argmax())))

plt.figure(figsize=(12, 5))
for nm, style in [('总体', 'k-o'), ('2012段', '--'), ('2014段', '--'), ('2015段', '--')]:
    plt.plot(range(48), curves[nm], style, ms=3, label=nm)
plt.xticks(range(48), [hhmm(s) for s in range(48)], rotation=90, fontsize=7)
plt.axvspan(8, 11, color='gray', alpha=0.2, label='凌晨低谷应在此')
plt.axvspan(15, 19, color='orange', alpha=0.15, label='早高峰')
plt.axvspan(35, 39, color='red', alpha=0.12, label='晚高峰')
plt.legend(); plt.title('完整日内曲线(网格穿越流量)')
plt.tight_layout(); plt.savefig('diag_daily_curve.png', dpi=110)
