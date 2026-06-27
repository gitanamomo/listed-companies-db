import akshare as ak

# Test 1: stock_individual_info_em
print("=== stock_individual_info_em ===")
try:
    df = ak.stock_individual_info_em(symbol='000001')
    cols = df['item'].tolist()
    vals = df['value'].tolist()
    d = dict(zip(cols, vals))
    print(f"Columns: {cols}")
    for k in ['省份','城市','所属行业','总市值','流通市值']:
        if k in d: print(f"  {k}: {d[k]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 2: stock_profile_cninfo
print("\n=== stock_profile_cninfo ===")
try:
    df = ak.stock_profile_cninfo(symbol='000001')
    addr = df['注册地址'].iloc[0] if '注册地址' in df.columns else 'N/A'
    print(f"  注册地址: {addr[:60]}")
except Exception as e:
    print(f"  ERROR: {e}")
