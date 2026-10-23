# 需求实施计划

- [x] 1. 搭建项目骨架与测试框架
  - 创建 `backend/`（FastAPI + SQLite）与 `frontend/`（Vite + Vue3）目录
  - 后端入口 `backend/app/main.py` 挂载 `/api`，生产期托管前端静态资源
  - 前端 `vite.config.ts`：`server.proxy['/api']` 指向 `http://127.0.0.1:8000`，`server.allowedHosts: ['.monkeycode-ai.online']`
  - 统一 API 返回 `{code, message, data}`（design.md §3.1）
  - 设置 pytest（backend）与 Vitest（frontend）
  - 对应：R20、design.md §2

- [x] 2. 实现数据模型与 SQLite
  - [x] 2.1 按 design.md §4 建表：container_type、package_master、task、import_row、packing_run、packing_plan、container_instance、placement、export_template、app_setting
    - 尺寸入库 mm、重量 kg；`import_row.filled_fields_json` 记录主数据补全字段
  - [x] 2.2 实现仓储层 CRUD 与引用校验（删除被引用箱型返回 409）
    - 对应：R7、R21、R22
  - [x] 2.3 为仓储层编写单元测试
    - 唯一约束、引用禁删、任务 round-trip

- [x] 3. 实现箱型库 API 与预置数据
  - [x] 3.1 实现 GET/POST/PUT/DELETE `/api/container-types` 及 Excel 导入导出
    - 预置 20GP、40GP、40HQ（内部尺寸与载重按 design.md / PRD §4.1）
    - 代码唯一、正数校验、容积自动计算可覆盖、停用后新任务不可选、引用后禁删改停用
    - 对应：R21
  - [x] 3.2 为箱型库编写单元测试
    - 预置三条、代码冲突、引用禁删

- [x] 4. 实现包装主数据 API
  - [x] 4.1 实现 GET/POST/PUT/DELETE `/api/packages`
    - 字段含 PN、PackMatls、长宽高、三重量、旋转/易压/同种堆叠/装卸/堆码层数
    - PN 已填则唯一；停用后新任务不可选
    - 对应：R22
  - [x] 4.2 为包装主数据编写单元测试

- [x] 5. 实现任务、导入补全与编码防线
  - [x] 5.1 实现任务 CRUD `/api/tasks`
    - 保存名称、创建时间、params/rules/site_groups/container_mode、adopted 与 last_ok 方案
    - 对应：R7
  - [x] 5.2 实现 POST `/api/tasks/{id}/import`：xlsx 17 列映射（R25）
    - 长宽高 cm→mm、重量 kg；N 列导入忽略
    - 长宽高齐全用表值；缺尺寸 PN 优先、PN 空再用 PackMatls 补全空缺字段
    - 都不命中则标红、列出缺失 PN/PackMatls、阻止开算
  - [x] 5.3 实现编码识别与乱码防护（R28）
    - 导入按 UTF-8 / BOM / GBK 探测；导出全程 xlsx；CSV 兜底 `utf-8-sig`；中文文件名 RFC 5987
  - [x] 5.4 实现待填表导出、批量维护入库、重新匹配
    - POST `/api/tasks/{id}/import/batch-maintain`、`/re-match`；完整行可按 PackMatls 入库
    - 对应：R25
  - [x] 5.5 为导入补全与编码编写单元测试（必做，防坑）
    - 样表 IB-1 用表值、VEN 按 PN 补全、缺规格拦截、UTF-8/BOM/GBK、中文表头往返

- [x] 6. 实现 Site 确认与全局参数
  - [x] 6.1 GET/PUT `/api/tasks/{id}/site-groups`：按 Site 聚合、默认不选、同柜/分离互斥、随任务保存
    - 对应：R13、R26
  - [x] 6.2 GET/PUT `/api/settings`：人工上限 30 kg、铲齿 1220 mm、时限 60 s、间隙 0
    - 对应：R9、R18
  - [x] 7. 检查点 - 确保所有测试通过
    - 确保所有测试通过,如有疑问请询问用户
    - M1 验收：样表可导入、VEN 按 PN 补全、缺规格拦截、中文无乱码

- [x] 8. 实现 packing_engine 几何与规则校验器
  - [x] 8.1 实现 model.py / geometry.py：CargoItem、AABB 相交、包围盒、支撑判定
    - 对应：design.md §5.2
  - [x] 8.2 实现 rules.py 全部校验器
    - bounds、collision、payload、weight_order（R10）、crush（R11）、same_type_stack（R12）、fork_tine（R18）、manual_limit（R9）、pn_continuous（R8）、inside_out（R17）
    - 冲突优先级与降级记录（R14）
  - [x] 8.3 为规则校验器编写单元测试（必做）
    - 各校验器真值表；P1 不相交、P8 铲齿、P9 轻重

- [x] 9. 实现默认摆放算法、KPI 与固定箱型
  - [x] 9.1 实现 groups.py：Site 同柜组不可拆、PN 连续链排序
    - 对应：R8、R13
  - [x] 9.2 实现 place.py 中 DBLF 与 MaximalSpace，复用同一 checkers 链
    - 对应：R16 默认算法、R17 由内向外
  - [x] 9.3 实现 kpi.py 单箱与整体公式（唯一实现处）
    - 整体体积利用率 = Σ已装体积 / Σ已用箱容积；载重同理；完成率 = 已分配/总数；便利性与约束满足率按件数加权；耗时取最大
    - 整体必须可由单箱复算（P3、R30）
  - [x] 9.4 实现 runner.py 固定箱型模式调度、时限、ProgressReporter
    - 对应：R2、R19 固定、R31
  - [x] 9.5 为 KPI 对账、DBLF 金样本、固定箱量不足编写单元测试（必做）
    - 场景 8/16；P3/P4
  - [x] 10. 检查点 - 确保所有测试通过
    - 确保所有测试通过,如有疑问请询问用户
    - M2 验收：样表出方案、KPI 逐项复算一致、规则单测全绿

- [x] 11. 实现完整计算：自由组合、其余算法、作业 API
  - [x] 11.1 实现 ExtremePoint、WallBuild、Guillotine，全部走同一 checkers
    - 对应：R16
  - [x] 11.2 实现 freemix.py：下界估计、有界枚举、箱型/数量锁定、无解提示
    - 对应：R19
  - [x] 11.3 实现 POST `/api/tasks/{id}/compute` 与 GET `/api/jobs/{id}`
    - 线程池并行算法、>3s 上报 progress 与 eta_seconds、超时部分方案 + timed_out
    - 对应：R16、R31
  - [x] 11.4 实现方案列表、采用方案、placements 查询
    - GET `/api/tasks/{id}/plans`、PUT adopted、GET `/api/plans/{id}/placements`
    - 未分配件也落 placement 行
    - 对应：R2、R15
  - [x] 11.5 为自由组合锁定无解、多算法超时编写集成测试
  - [x] 12. 检查点 - 确保所有测试通过
    - 确保所有测试通过,如有疑问请询问用户
    - M3 验收：锁定/无解/对照表符合 R19/R16；各算法进度与 ETA 正确

- [x] 13. 实现导出回写、导出模板与 3D
  - [x] 13.1 实现默认导出：A–Q 回写（N 覆盖为 `{箱型}-{序号}`）、新增每柜从 1 重排的装箱顺序、未分配两列留空、附加未分配明细与用箱摘要（单箱+整体 KPI）
    - 对应：R4、R27、R30
  - [x] 13.2 实现导出模板 CRUD；默认模板不可删；列字段/顺序/列宽/对齐/数字格式
    - 对应：R5
  - [x] 13.3 实现前端 View3D：每箱页签、选中按包围盒居中工作区、0.5/1/2/4 倍速回放、步进、点选高亮
    - 对应：R6、R29
  - [x] 13.4 为回写 diff（P10）与编码导出编写单元测试（必做）
    - 场景 1/14
  - [x] 14. 检查点 - 确保所有测试通过
    - 确保所有测试通过,如有疑问请询问用户
    - M4 验收：N 列覆盖、每柜顺序、3D 居中与倍速

- [x] 15. 实现前端全站页面与极简 UI
  - [x] 15.1 实现页面：任务列表/详情、导入预览、Site 确认、规则配置、箱型库、包装主数据、KPI 对照、导出模板、全局参数、JobProgress
    - 暖白背景、深灰文字、单强调色、四级标题、统一对齐、每区一个主按钮
    - 对应：R3、R14、R23、R31
  - [x] 15.2 规则开关与优先级拖拽排序，默认顺序：Site 同柜 → PN 连续 → Site 分离 → 同种堆叠 → 易压 → 轻重 → 装卸
    - 对应：R3、R14
  - [x] 15.3 箱型模式扩展 UI：ImportPreview 固定多箱型数量表 / 自由组合 勾选+qty_lock+max_qty；TaskList modeLabel 与 TaskDetail modeSummary 支持新结构
    - 对应：R19 AC1-AC8

- [x] 16. 实现 Windows 可执行启动
  - [x] 16.1 启动脚本：探测空闲端口、拉起 FastAPI、打开默认浏览器、数据目录持久化 SQLite、关闭进程停止服务
    - 对应：R24
  - [x] 16.2 编写 PyInstaller 打包配置
  - [x] 17. 检查点 - 确保所有测试通过
    - 确保所有测试通过,如有疑问请询问用户
    - M5 验收：全链路回归（场景 1–17 可自动化部分）全绿
