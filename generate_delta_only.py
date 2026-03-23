import pandas as pd
import os

# 파일 경로 설정
FILE_NEW = "CR_All_Data_Latest.xlsx"
FILE_OLD = "CR_All_Data_Latest_Old.xlsx" # OneDrive 버전 기록 등에서 복구한 이전 파일을 이 이름으로 저장하세요.
FILE_REPORT = "CR_Delta_Report_Fixed.xlsx"

def generate_delta_report(old_df, new_df, supercat_name):
    changes = []
    pcol = 'Product' if 'Product' in new_df.columns else (new_df.columns[2] if len(new_df.columns) > 2 else None)
    if pcol is None: return changes

    # 중량, 메모리, 용량 등 제품 사양을 구분할 수 있는 컬럼들 추가 식별자로 사용
    spec_cols = ['Memory', 'Storage', 'Processor model name', 'Processor', 'Display size']
    actual_specs = [c for c in spec_cols if c in new_df.columns or (not old_df.empty and c in old_df.columns)]
    id_cols = [pcol] + actual_specs

    # 중복 제거 및 인덱스 설정
    def prepare_m(df, cols):
        if df.empty: return pd.DataFrame()
        d = df.copy()
        for c in cols:
            if c in d.columns:
                d[c] = d[c].fillna('').astype(str).str.strip()
            else:
                d[c] = ''
        return d.drop_duplicates(subset=cols).set_index(cols)

    old_m = prepare_m(old_df, id_cols)
    new_m = prepare_m(new_df, id_cols)

    skip = {'Extracted_At', 'Category', 'SuperCategory', 'Price'} | set(id_cols)
    comp_cols = [c for c in new_df.columns if c not in skip]

    for model in new_m.index:
        cat = new_m.loc[model, 'Category']
        nt = new_m.loc[model, 'Extracted_At']
        if old_m.empty or model not in old_m.index:
            changes.append({"SuperCategory": supercat_name, "Category": cat, "Product": model,
                            "Attribute": "New Model", "Previous": "N/A", "New": "Added",
                            "Old Extracted_At": "N/A", "New Extracted_At": nt})
        else:
            ot = old_m.loc[model, 'Extracted_At']
            for col in comp_cols:
                if col in new_m.columns and col in old_m.columns:
                    val_new = new_m.loc[model, col]
                    val_old = old_m.loc[model, col]

                    vn = str(val_new).strip()
                    vo = str(val_old).strip()
                    
                    # 빈 값(결측치)들을 동일하게 취급 (예: 'nan', 'NA', 'None', '')
                    empty_vals = {"", "nan", "na", "none", "n/a", "-"}
                    if vn.lower() in empty_vals and vo.lower() in empty_vals:
                        continue
                    
                    # 소수점 표시 형식 차이로 인한 오탐지 방지 (예: 84.0과 84를 같게 취급)
                    if pd.notna(val_new) and pd.notna(val_old):
                        try:
                            if float(val_new) == float(val_old):
                                continue
                        except (ValueError, TypeError):
                            pass
                    
                    if vn != vo:
                        changes.append({"SuperCategory": supercat_name, "Category": cat, "Product": model,
                                        "Attribute": col, "Previous": vo, "New": vn,
                                        "Old Extracted_At": ot, "New Extracted_At": nt})
    return changes

def main():
    if not os.path.exists(FILE_NEW):
        print(f"Error: {FILE_NEW} 파일이 없습니다.")
        return

    if not os.path.exists(FILE_OLD):
        print(f"Notice: {FILE_OLD} 파일이 없습니다. Delta 보고서를 생성하려면 이전 데이터를 이 이름으로 준비하세요.")
        print("OneDrive를 사용 중이시라면 'CR_All_Data_Latest.xlsx'의 '버전 기록'에서 어제 파일을 다운로드하여 이름을 바꾸시면 됩니다.")
        return

    print("데이터 로딩 중...")
    xl_new = pd.ExcelFile(FILE_NEW)
    xl_old = pd.ExcelFile(FILE_OLD)
    
    all_changes = []
    
    for sheet in xl_new.sheet_names:
        print(f"Processing sheet: {sheet}")
        df_new = xl_new.parse(sheet)
        df_old = xl_old.parse(sheet) if sheet in xl_old.sheet_names else pd.DataFrame()
        all_changes.extend(generate_delta_report(df_old, df_new, sheet))

    if all_changes:
        pd.DataFrame(all_changes).to_excel(FILE_REPORT, index=False)
        print(f"Success: {len(all_changes)}건의 변경사항이 {FILE_REPORT}에 저장되었습니다.")
    else:
        print("변경사항이 없습니다.")

if __name__ == "__main__":
    main()
