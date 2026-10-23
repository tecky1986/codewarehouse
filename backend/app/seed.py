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


def seed_if_empty(conn) -> None:
    from app.repos import ContainerTypeRepo, SettingRepo, ExportTemplateRepo

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
