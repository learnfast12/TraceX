import pandas as pd

dd = pd.read_excel('/home/x0_shravan_0x/Downloads/Description_1_.xlsx', sheet_name='Data_Dicitionary')

top_features = ['F1813', 'F1597', 'F3799', 'F1594', 'F1989', 'F949', 'F2652',
                 'F3226', 'F3755', 'F3811', 'F3529', 'F3897', 'F1489', 'F1015',
                 'F2447', 'F3445', 'F2340', 'F3805', 'F1865', 'F3287']

result = dd[dd['Feature'].isin(top_features)][['Feature', 'Variable Name', 'Description']]
result = result.set_index('Feature').reindex(top_features).reset_index()
print(result.to_string(index=False))
