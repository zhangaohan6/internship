import pandas as pd
import numpy as np
from typing import Optional


# -------------------------- 1. 基础工具函数 --------------------------


def _make_datetime_from_diff_and_hms(
    df: pd.DataFrame,
    diff_col: str,
    time_col: str,
    base_date: str = "2000-01-01",
) -> pd.Series:
    """
    用 *_datediff + *_hms 拼出真正的 Timestamp.
    - diff_col: 相对天数（整数）
    - time_col: "HH:MM:SS" 字符串
    """
    if diff_col not in df.columns or time_col not in df.columns:
        return pd.Series(pd.NaT, index=df.index)

    days = pd.to_numeric(df[diff_col], errors="coerce")
    base = pd.Timestamp(base_date)

    # 时间字符串缺失时用 "00:00:00"
    hms = df[time_col].fillna("00:00:00").astype(str)

    try:
        td_days = pd.to_timedelta(days, unit="D")
        td_time = pd.to_timedelta(hms)
        return base + td_days + td_time
    except Exception:
        return pd.Series(pd.NaT, index=df.index)


# -------------------------- 2. 去标识化（轻量处理） --------------------------


def desensitize_anzhfr_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    去掉明显的个人标识字段，并预留医院编码。
    datathon 的数据已经基本匿名，这里只是防御性地再删一次。
    """
    df = df.copy()

    # 可能出现的人名、联系方式字段（不存在就自动忽略）
    id_cols = [
        "Name", "Surname", "MRN", "phone", "email", "medicare",
        "NHI", "address", "postcode",
    ]
    df = df.drop(columns=[c for c in id_cols if c in df.columns], errors="ignore")

    # 统一医院层级字段名称（后面方便用）
    if "Ahoscode" in df.columns:
        df["hospital_level"] = df["Ahoscode"].astype(str)
    elif "ahos_code" in df.columns:
        df["hospital_level"] = df["ahos_code"].astype(str)
    else:
        df["hospital_level"] = "Unknown"

    return df


# -------------------------- 3. 基础清洗 --------------------------


def clean_anzhfr_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    依据原始字段结构做基础清洗：
    - 保留任务 1/2 会用到的核心字段
    - 处理 age、重要编码变量的类型和异常值
    - 保留 *_datediff / *_hms 方便后面生成时间
    """
    df = df.copy()

    # 3.1 选取核心字段（按你贴的头几列来）
    core_cols = [
        # 时间差 & 时间（用于后面构造 Timestamp）
        "tarrdatetime_datediff", "tarrdatetime_hms",
        "arrdatetime_datediff", "arrdatetime_hms",
        "depdatetime_datediff", "depdatetime_hms",
        "admdatetimeop_datediff", "admdatetimeop_hms",
        "sdatetime_datediff", "sdatetime_hms",
        "gdate_datediff", "wdisch_datediff", "hdisch_datediff",

        # 关键信息
        "age", "sex", "ptype", "uresidence",
        "e_dadmit",          # admission via ED of operating hospital
        "ftype", "surg", "asa", "frailty",
        "wdest", "dresidence", "fresidence2",
        "mort30d", "mort90d", "mort120d", "mort365d",

        # 可能有的区域字段（仅用于 ED 阈值，不再输出 state 维度）
        "Area", "area",

        # 你后面可能用到的一些过程变量（暂时只是保留）
        "walk", "cogstat", "bonemed", "gerimed",
    ]
    keep_cols = [c for c in core_cols if c in df.columns] + [
        c for c in ["hospital_level"] if c in df.columns
    ]
    df = df[keep_cols].copy()

    # 3.2 年龄处理：转数值 + 异常值 → NaN + 按年龄段中位数填补
    if "age" in df.columns:
        df["age"] = pd.to_numeric(df["age"], errors="coerce")
        # registry 只收 50 岁以上，>110 也视作异常
        df.loc[(df["age"] < 50) | (df["age"] > 110), "age"] = np.nan

        # 年龄分组
        df["age_group"] = pd.cut(
            df["age"],
            bins=[49, 64, 79, 120],
            labels=["50-64", "65-79", "≥80"],
            right=True,
        )

        # 每个年龄段内用中位数填补缺失
        def _fill_group_median(s: pd.Series) -> pd.Series:
            med = s.median()
            return s.fillna(med)

        df["age"] = df.groupby("age_group", observed=True)["age"].transform(
            _fill_group_median
        )

    # 3.3 关键编码变量统一转成数值（保留 NaN，不用 "Unknown" 字符串）
    for col in ["e_dadmit", "surg", "asa", "frailty", "mort30d", "wdest"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # sex 也转一下，方便后面统计
    if "sex" in df.columns:
        df["sex"] = pd.to_numeric(df["sex"], errors="coerce")

    return df


# -------------------------- 4. 特征构造：时间、ED、手术等 --------------------------


def extract_anzhfr_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    基于 *_datediff + *_hms 构造：
    - arr_dt / dep_dt / tarr_dt / inpt_fracture_dt / surg_dt
    - ED 停留时间 & 是否达标
    - time_to_surgery_hours & within_24h_surgery
    - hospital_level
    - mortality_30d / discharge_destination
    """
    df = df.copy()

    # 4.1 构造几个关键时间点
    df["arr_dt"] = _make_datetime_from_diff_and_hms(
        df, "arrdatetime_datediff", "arrdatetime_hms"
    )
    df["dep_dt"] = _make_datetime_from_diff_and_hms(
        df, "depdatetime_datediff", "depdatetime_hms"
    )
    df["tarr_dt"] = _make_datetime_from_diff_and_hms(
        df, "tarrdatetime_datediff", "tarrdatetime_hms"
    )
    df["inpt_fracture_dt"] = _make_datetime_from_diff_and_hms(
        df, "admdatetimeop_datediff", "admdatetimeop_hms"
    )
    df["surg_dt"] = _make_datetime_from_diff_and_hms(
        df, "sdatetime_datediff", "sdatetime_hms"
    )

    # 4.2 计算 ED 停留时间和是否达标（只对通过 ED 的入院计算）
    df["ed_stay_hours"] = np.nan

    if "arr_dt" in df.columns and "dep_dt" in df.columns:
        # e_dadmit 1/2/4 表示通过 ED（包括转院）
        if "e_dadmit" in df.columns:
            ed_mask = df["e_dadmit"].isin([1, 2, 4])
        else:
            ed_mask = df["arr_dt"].notna() & df["dep_dt"].notna()

        valid = ed_mask & df["arr_dt"].notna() & df["dep_dt"].notna()
        df.loc[valid, "ed_stay_hours"] = (
            df.loc[valid, "dep_dt"] - df.loc[valid, "arr_dt"]
        ).dt.total_seconds() / 3600.0

        # 负值当作错误，置为 NaN
        df.loc[df["ed_stay_hours"] < 0, "ed_stay_hours"] = np.nan

    # ED 达标：若有 Area=10 则按 NZ 6 小时阈值，否则 4 小时；没 Area 信息统一按 4 小时
    df["ed_stay_compliant"] = "Unknown"

    if "ed_stay_hours" in df.columns:
        # 判断 Area 列
        area_col: Optional[str] = None
        if "Area" in df.columns:
            area_col = "Area"
        elif "area" in df.columns:
            area_col = "area"

        if area_col:
            is_nz = df[area_col] == 10  # 10 = New Zealand
            # 澳洲（非 NZ）
            aus_mask = ~is_nz & df["ed_stay_hours"].notna()
            df.loc[aus_mask & (df["ed_stay_hours"] <= 4), "ed_stay_compliant"] = "Yes"
            df.loc[aus_mask & (df["ed_stay_hours"] > 4), "ed_stay_compliant"] = "No"

            # 新西兰
            nz_mask = is_nz & df["ed_stay_hours"].notna()
            df.loc[nz_mask & (df["ed_stay_hours"] <= 6), "ed_stay_compliant"] = "Yes"
            df.loc[nz_mask & (df["ed_stay_hours"] > 6), "ed_stay_compliant"] = "No"
        else:
            # 没区域信息：统一 4 小时阈值
            df["ed_stay_compliant"] = np.select(
                [
                    df["ed_stay_hours"].isna(),
                    df["ed_stay_hours"] <= 4,
                ],
                ["Unknown", "Yes"],
                default="No",
            )

    # 4.3 time_zero（计算手术时间起点）
    df["time_zero"] = pd.NaT

    if "e_dadmit" in df.columns:
        # 1/2/4: 经 ED（包括转院），起点 = tarr_dt
        mask_ed = df["e_dadmit"].isin([1, 2, 4])
        df.loc[mask_ed, "time_zero"] = df.loc[mask_ed, "tarr_dt"]

        # 3: 住院病人骨折，起点 = inpt_fracture_dt
        mask_inpt = df["e_dadmit"] == 3
        df.loc[mask_inpt, "time_zero"] = df.loc[mask_inpt, "inpt_fracture_dt"]

    # 起点缺失的，再退一步用 arr_dt
    df["time_zero"] = df["time_zero"].fillna(df.get("arr_dt"))

    # 4.4 计算 time_to_surgery_hours
    df["time_to_surgery_hours"] = np.nan
    if "surg_dt" in df.columns:
        valid_time = df["time_zero"].notna() & df["surg_dt"].notna()
        df.loc[valid_time, "time_to_surgery_hours"] = (
            df.loc[valid_time, "surg_dt"] - df.loc[valid_time, "time_zero"]
        ).dt.total_seconds() / 3600.0

        # 负值当错误处理
        df.loc[df["time_to_surgery_hours"] < 0, "time_to_surgery_hours"] = np.nan

    # 4.5 within_24h_surgery，只对「真正做了手术」的患者
    df["within_24h_surgery"] = "Unknown"
    had_surgery_mask = pd.Series(False, index=df.index)

    if "surg" in df.columns:
        # 数据字典中 surg 是具体术式编码，这里保守认为 2–8 都是「做了手术」
        had_surgery_mask = df["surg"].isin([2, 3, 4, 5, 6, 7, 8])

    # 未手术或未知：标记为 Not applicable
    df.loc[~had_surgery_mask, "within_24h_surgery"] = "Not applicable"
    df.loc[~had_surgery_mask, "time_to_surgery_hours"] = np.nan

    # 做了手术 + 有有效 time_to_surgery
    valid_surg = had_surgery_mask & df["time_to_surgery_hours"].notna()
    df.loc[
        valid_surg & (df["time_to_surgery_hours"] <= 24),
        "within_24h_surgery",
    ] = "Yes"
    df.loc[
        valid_surg & (df["time_to_surgery_hours"] > 24),
        "within_24h_surgery",
    ] = "No"

    # 如果之前没设医院层级，这里再兜底一次
    if "hospital_level" not in df.columns:
        if "Ahoscode" in df.columns:
            df["hospital_level"] = df["Ahoscode"].astype(str)
        elif "ahos_code" in df.columns:
            df["hospital_level"] = df["ahos_code"].astype(str)
        else:
            df["hospital_level"] = "Unknown"

    # 4.6 30 天死亡 & 出院去向（友好标签）
    mort_col = None
    for c in df.columns:
        if c.lower() == "mort30d":
            mort_col = c
            break

    if mort_col is not None:
        df["mortality_30d"] = df[mort_col].map({
            1: "Alive",
            2: "Deceased",
        }).fillna("Unknown")
    else:
        df["mortality_30d"] = "Unknown"

    if "wdest" in df.columns:
        df["discharge_destination"] = df["wdest"].map({
            1: "Private Residence",
            2: "Nursing Home",
            3: "Public Rehabilitation",
            4: "Private Rehabilitation",
            5: "Other Hospital",
            6: "Deceased",
        }).fillna("Unknown")
    else:
        df["discharge_destination"] = "Unknown"

    return df


# -------------------------- 5. 适配 Dashboard 的轻量标准化 --------------------------


def standardize_anzhfr_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    dashboard 用轻量标准化：
    - 确保连续变量是 float（不做 MinMax 缩放）
    - 生成 asa_encoded / frailty_encoded 数值编码
    - 删除辅助列（age_group、time_zero、各种中间时间列）
    """
    df = df.copy()

    # 连续变量转 float
    for col in ["age", "time_to_surgery_hours", "ed_stay_hours"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # asa / frailty 数值编码
    if "asa" in df.columns:
        df["asa_encoded"] = pd.to_numeric(df["asa"], errors="coerce")
    else:
        df["asa_encoded"] = np.nan

    if "frailty" in df.columns:
        df["frailty_encoded"] = pd.to_numeric(df["frailty"], errors="coerce")
    else:
        df["frailty_encoded"] = np.nan

    # 删除不需要输出到 dashboard 的临时列
    drop_cols = [
        "age_group", "time_zero",
        "arr_dt", "dep_dt", "tarr_dt", "inpt_fracture_dt", "surg_dt",
        "tarrdatetime_datediff", "tarrdatetime_hms",
        "arrdatetime_datediff", "arrdatetime_hms",
        "depdatetime_datediff", "depdatetime_hms",
        "admdatetimeop_datediff", "admdatetimeop_hms",
        "sdatetime_datediff", "sdatetime_hms",
        "gdate_datediff", "wdisch_datediff", "hdisch_datediff",
        "Area", "area",
    ]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    return df


# -------------------------- 6. 总入口函数 --------------------------


def preprocess_anzhfr_dashboard_data(
    raw_data_path: str,
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    整体预处理流程：
    1) 读原始 csv
    2) 去标识化
    3) 基础清洗（类型 / 异常值）
    4) 特征构造（时间、ED、手术、出院等）
    5) 轻量标准化，输出给 dashboard
    """
    df_raw = pd.read_csv(raw_data_path)

    df = desensitize_anzhfr_data(df_raw)
    df = clean_anzhfr_data(df)
    df = extract_anzhfr_features(df)
    df = standardize_anzhfr_data(df)

    if output_path is not None:
        df.to_csv(output_path, index=False)

    return df


if __name__ == "__main__":
    # 使用示例：
    cleaned = preprocess_anzhfr_dashboard_data(
        "unsw_datathon_2025.csv",
        "anzhfr_dashboard_ready.csv"
    )
    cleaned.to_json("anzfr_dashboard_ready.json", orient="records")
    print(cleaned.head())
