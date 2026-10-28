PRESET_CONTAINER_TYPES = [
    {
        "code": "20GP",
        "name": "20GP",
        "iso_code": "22G1",
        "inner_l": 5898,
        "inner_w": 2352,
        "inner_h": 2393,
        "door_w": 2340,
        "door_h": 2280,
        "max_payload": 28200,
        "tare_weight": 2200,
        "freight_price": 0,
        "enabled": 1,
        "remark": "preset",
    },
    {
        "code": "40GP",
        "name": "40GP",
        "iso_code": "42G1",
        "inner_l": 12032,
        "inner_w": 2352,
        "inner_h": 2393,
        "door_w": 2340,
        "door_h": 2280,
        "max_payload": 26700,
        "tare_weight": 3800,
        "freight_price": 0,
        "enabled": 1,
        "remark": "preset",
    },
    {
        "code": "40HQ",
        "name": "40HQ",
        "iso_code": "45G1",
        "inner_l": 12032,
        "inner_w": 2352,
        "inner_h": 2698,
        "door_w": 2340,
        "door_h": 2585,
        "max_payload": 26700,
        "tare_weight": 3900,
        "freight_price": 0,
        "enabled": 1,
        "remark": "preset",
    },
]


DEFAULT_SETTINGS = {
    "manual_limit_kg": "30",
    "fork_tine_mm": "1220",
    "time_limit_s": "60",
    "gap_mm": "0",
}


# 示例数据：空库首次启动时写入，便于试用导入与匹配流程
SAMPLE_PACKAGES = [
    {
        "pn": None,
        "name": "OUTCASE(IB-1)",
        "package_type": "OUTCASE(IB-1)",
        "l": 1460,
        "w": 1150,
        "h": 1100,
        "volume": 1.85,
        "tare": 136.0,
        "net": 256.0,
        "gross": 392.0,
        "max_load": 500.0,
        "remark": "sample",
        "enabled": 1,
    },
    {
        "pn": "ACW1081490*80",
        "name": "OUTCASE(VEN)",
        "package_type": "OUTCASE(VEN)",
        "l": 600,
        "w": 400,
        "h": 400,
        "volume": 0.096,
        "tare": 12.0,
        "net": 58.0,
        "gross": 70.0,
        "max_load": 0,
        "remark": "sample",
        "enabled": 1,
    },
]

# 与示例 xlsx 一致的导入行（17 列 A–Q，N 列忽略）
SAMPLE_IMPORT_ROWS_HEADER = [
    "箱号 No", "长 Length", "宽 width", "高 high", "体积 CBM", "OUTCASE NO.",
    "PackMatls", "箱重/Tare weight", "净重 NET WEIGHT", "毛重 TOTAL WEIGHT",
    "PN", "备注", "Site", "集装箱号 ontBiner No", "关单号", "DN", "尺寸",
]
SAMPLE_IMPORT_ROWS = [
    # a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q
    [1, 146, 115, 110, 1.85, "5000931045", "OUTCASE(IB-1)", 136, 256, 392, None, None, "Canoas", None, None, 80129743, None],
    [2, 146, 115, 110, 1.85, "5000931071", "OUTCASE(IB-1)", 136, 524, 660, None, None, "Canoas", None, None, 80129743, None],
    [3, None, None, None, None, "5000931481", "OUTCASE(VEN)", None, None, None, "ACW1081490*80", None, "Canoas", None, None, 80129743, None],
    [4, None, None, None, None, "5000931482", "OUTCASE(VEN)", None, None, None, "ACW1081490*80", None, "Canoas", None, None, 80129743, None],
]


def seed_if_empty(conn, with_sample: bool = True) -> None:
    """Preload preset data. with_sample=False 跳过示例数据。"""
    from app.repos import (
        ContainerTypeRepo,
        PackageMasterRepo,
        SettingRepo,
        ExportTemplateRepo,
        ImportRowRepo,
        TaskRepo,
    )

    repo = ContainerTypeRepo(conn)
    if not repo.list_all():
        for item in PRESET_CONTAINER_TYPES:
            repo.create(item)
    settings = SettingRepo(conn)
    existing = settings.get_all()
    for k, v in DEFAULT_SETTINGS.items():
        if k not in existing:
            settings.put(k, v)

    templates = ExportTemplateRepo(conn)
    if not templates.list_all():
        from app.exporting import default_template_columns

        templates.create(
            {
                "name": "默认导出模板",
                "is_default": True,
                "columns_json": default_template_columns(),
            }
        )

    if not with_sample:
        return

    # 示例包装主数据
    pkg = PackageMasterRepo(conn)
    for item in SAMPLE_PACKAGES:
        pn = item.get("pn")
        if pn:
            if not pkg._get_pn_exact(pn):
                pkg.create(item)
        else:
            if not pkg.get_by_packmatls(item["package_type"]):
                pkg.create(item)

    # 示例任务 + 导入行
    from app.importing import map_raw_rows

    tasks = TaskRepo(conn)
    if not any(t["name"] == "示例任务" for t in tasks.list_all()):
        sample_task = tasks.create({"name": "示例任务"})
        rows = map_raw_rows([SAMPLE_IMPORT_ROWS_HEADER] + SAMPLE_IMPORT_ROWS)
        ImportRowRepo(conn).replace_for_task(sample_task["id"], rows)
