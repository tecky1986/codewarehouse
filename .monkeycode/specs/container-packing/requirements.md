# Requirements Document

## Introduction

集装箱装箱工具是一套 Web 应用，用于根据可配置规则将批量货物安排到集装箱中，并输出可导出的装箱方案与 3D 示意。用户通过浏览器维护专业箱型库与包装主数据，也可在任务中导入临时包装；系统按多种主流装箱算法计算方案，并以统一 KPI 评估结果。用户可在固定箱型与自由组合求最优之间选择，自由组合还可锁定允许的箱型或某箱型的数量。摆放顺序从箱内深处依次向外，叉车作业受铲齿长度约束。计算结果支持导出为 Excel，且导出表格的格式、表头与字段可自定义。装箱约束规则将分批补充，系统须支持规则的持续扩展与配置。

## Glossary

- **货物（Cargo）**: 待装入集装箱的单件或同类货件，包含尺寸、重量、数量及可旋转等属性。
- **集装箱（Container）**: 用于装载货物的箱体，包含箱型、内部尺寸、最大载重等属性。
- **装箱方案（Packing Plan）**: 一次计算产生的货物在集装箱内的摆放结果，包含位置、朝向、所属箱号等信息。
- **装箱规则（Packing Rule）**: 计算时必须满足的约束，例如同柜、装卸方式、轻重堆叠、承压、同种堆叠、目的地亲和与隔离等。
- **包装类型（Package Type）**: 货物的包装品类标识，例如 PackMatls；相同包装类型允许装入不同集装箱。
- **同柜组（Same-Container Group）**: 必须装入同一集装箱且禁止拆柜的货物集合；仅由用户在运算前勾选的 Site 同柜构成。
- **PN 连续装箱（PN Continuity）**: 相同 PN 的货物在装箱顺序上尽量连续：先填满当前柜，剩余部分接着装入下一柜。
- **Site**: 导入表中的站点/目的地列；默认不产生同柜或隔离约束，仅在用户勾选后生效。
- **PN**: 包装物料号，包装主数据的优先查找键。
- **PackMatls**: 包装名称，PN 为空时的次级查找键。
- **连续放置（Continuous Placement）**: 同一集装箱内，目标货物沿箱长方向占据一段连续区间，中间不插入该组以外的货物。
- **规则冲突优先级（Rule Conflict Priority）**: 当多条装箱规则对同一批货物给出互斥要求时，系统按用户勾选并排序的优先级决定遵守顺序。
- **装卸方式（Loading Method）**: 货物装入集装箱的作业方式，取值为叉车装箱或人工装箱。
- **人工装箱重量上限（Manual Loading Weight Limit）**: 允许采用人工装箱的单件重量上限，默认值为 30 kg。
- **易压货物（Crush-Sensitive Cargo）**: 顶部禁止再堆放其他货物的货件；该货件可以堆在其他货件之上，或独占一层。
- **同种堆叠货物（Same-Type Stack Cargo）**: 仅允许与货物类型相同的货件发生上下堆叠关系的货件。
- **导入模板（Import Template）**: 预先定义列结构的表格文件，用于批量导入货物、集装箱或其他输入数据。
- **导出模板（Export Template）**: 用户自定义的 Excel 输出结构，包含表头字段、列顺序、列宽及格式。
- **3D 示意（3D Preview）**: 以三维视图展示装箱方案中货物在集装箱内的空间位置与朝向。
- **装箱 KPI（Packing KPI）**: 衡量装箱方案质量的一组指标，包括体积利用率、载重利用率、用箱数、装载完成率、未分配量、作业便利性、约束满足率、重心偏移与计算耗时。
- **装箱算法（Packing Algorithm）**: 生成装箱方案的计算方法；系统内置多种主流算法，用户可选择一种或多种对比。
- **箱门（Container Door）**: 集装箱的装货开口端。
- **箱内深处（Inner End）**: 集装箱内与箱门相对的端壁。
- **由内向外（Inside-Out Loading）**: 先将货物放置于箱内深处，再依次向箱门方向填充，保证后续货物始终可从箱门侧取放。
- **铲齿长度（Fork Tine Length）**: 叉车货叉的有效插入长度，用于约束叉车装箱货物在进叉方向上的尺寸与可托举深度。
- **进叉方向（Fork Insertion Axis）**: 叉车货叉插入货物底部的方向，默认与箱长方向一致（从箱门指向箱内深处）。
- **箱型（Container Type）**: 集装箱的规格类别，例如 20GP、40GP、40HQ，包含内部尺寸与最大载重。
- **固定箱型模式（Fixed-Type Mode）**: 计算时只使用用户指定的箱型与数量，不增删箱型、不改数量。
- **自由组合模式（Free-Mix Mode）**: 计算时在允许的箱型集合内选择箱型与数量，按最优目标搜索用箱组合。
- **箱型锁定（Type Lock）**: 自由组合模式下，仅允许使用用户勾选的箱型。
- **数量锁定（Quantity Lock）**: 自由组合模式下，将某一箱型的使用数量固定为指定值。
- **最优目标（Optimization Objective）**: 自由组合搜索时所优化的主指标，默认为装载完成率最高，其次用箱数最少，再次体积利用率最高。
- **箱型库（Container Type Library）**: 系统级箱型主数据，供固定箱型模式与自由组合模式引用。
- **包装主数据（Package Master）**: 预先定义并持久保存的包装规格，含尺寸、重量及规则相关属性，可被多个任务引用。
- **临时包装（Temporary Package）**: 仅在当前装箱任务内有效的包装规格，由导入或任务内新建产生，默认不写入包装主数据。
- **强调色（Accent Color）**: 界面中唯一用于突出核心操作与关键状态的颜色，全站仅使用这一种强调色。
- **Windows 启动程序（Windows Launcher）**: 在 Windows 上双击即可启动本系统的可执行文件，启动后在本机拉起 Web 服务并打开浏览器。
- **系统（System）**: 本集装箱装箱工具，以 Web 应用形式在浏览器中使用，并在 Windows 上通过可执行文件启动。

## Requirements

### Requirement 1: 模板导入与批量数据上传

**User Story:** AS 装箱计划人员, I want 通过格式化模板批量导入货物和集装箱数据, so that 无需手工逐条录入即可开始计算。

#### Acceptance Criteria

1. THE System SHALL 提供可下载的导入模板，模板包含货物与集装箱所需字段及示例行。
2. WHEN 用户选择符合模板结构的文件并上传, THE System SHALL 解析文件中的全部数据行并生成导入预览。
3. IF 某行数据缺少必填字段、类型不匹配或数值超出允许范围, THE System SHALL 在预览中标出该行及错误原因，并允许用户修正后重新导入。
4. WHEN 导入预览通过校验, THE System SHALL 将校验通过的数据写入当前装箱任务。
5. THE System SHALL 支持一次导入多条货物记录与多条集装箱记录。

### Requirement 2: 按规则计算装箱方案

**User Story:** AS 装箱计划人员, I want 系统按已配置规则计算货物在集装箱中的摆放, so that 方案满足业务约束并可直接用于安排装柜。

#### Acceptance Criteria

1. WHEN 当前任务已具备货物数据、集装箱数据及至少一条启用的装箱规则, THE System SHALL 生成装箱方案，方案中每件已分配货物包含所属集装箱、空间坐标与朝向。
2. WHILE 计算装箱方案, THE System SHALL 对每件已分配货物校验全部已启用的装箱规则。
3. IF 部分货物在全部可用集装箱内均无法满足已启用规则, THE System SHALL 将这部分货物标记为未分配，并给出未分配原因。
4. THE System SHALL 允许用户查看每次计算使用的规则集合、所选算法及装箱 KPI。
5. THE System SHALL 支持后续以配置方式新增、启用、停用装箱规则，且新增规则在启用后参与下一次计算。

### Requirement 3: 装箱规则配置

**User Story:** AS 规则管理员, I want 以可配置方式维护装箱约束, so that 已录入及后续补充的规则能直接作用于计算。

#### Acceptance Criteria

1. THE System SHALL 以规则清单形式展示全部装箱规则，每条规则包含名称、说明、启用状态。
2. WHEN 用户启用或停用某条规则, THE System SHALL 在下一次计算中按更新后的启用集合执行。
3. THE System SHALL 将装箱规则与具体货物、集装箱数据分离存储，使规则变更无需重新设计导入模板。
4. THE System SHALL 在导入模板中提供规则所需的货物属性字段，字段集合与样表列及包装主数据字段对齐，详见 Requirement 25。
5. 后续补充的约束须作为本需求之后的独立 Requirement 写入本文档。

### Requirement 4: 计算结果导出为 Excel

**User Story:** AS 装箱计划人员, I want 将装箱方案导出为 Excel, so that 结果可交给现场或下游系统使用。

#### Acceptance Criteria

1. WHEN 当前任务存在已完成的装箱方案, THE System SHALL 允许用户将方案导出为 `.xlsx` 文件。
2. THE System SHALL 在导出文件中包含已分配货物明细、未分配货物明细及集装箱使用摘要。
3. WHEN 用户已选择一个导出模板, THE System SHALL 按该模板的表头、字段顺序与列格式生成 Excel 文件。
4. IF 用户未选择导出模板, THE System SHALL 使用系统默认导出模板生成 Excel 文件。

### Requirement 5: 自定义导出表格格式

**User Story:** AS 装箱计划人员, I want 自定义导出表头字段、列顺序与单元格格式, so that 导出文件符合各业务方的表格规范。

#### Acceptance Criteria

1. THE System SHALL 允许用户创建、编辑、复制、删除导出模板。
2. WHEN 用户编辑导出模板, THE System SHALL 允许从可选字段集合中选择表头字段，并指定列顺序。
3. THE System SHALL 允许用户为导出模板中的每一列设置列宽、对齐方式与数字格式。
4. WHEN 用户保存导出模板, THE System SHALL 将该模板与当前用户或当前任务关联，供后续导出重复使用。
5. THE System SHALL 提供至少一个系统默认导出模板，且该模板不可删除。

### Requirement 6: 3D 装箱示意

**User Story:** AS 装箱计划人员, I want 以 3D 视图查看装箱方案, so that 能直观核对货物在箱内的位置与朝向。

#### Acceptance Criteria

1. WHEN 当前任务存在已完成的装箱方案, THE System SHALL 以 3D 视图展示所选集装箱内全部已分配货物的位置、尺寸与朝向。
2. THE System SHALL 允许用户旋转、平移、缩放 3D 视图。
3. WHEN 用户在 3D 视图中选中一件货物, THE System SHALL 高亮该货物并显示该货物的标识、尺寸、重量与坐标。
4. THE System SHALL 允许用户在多个已使用集装箱之间切换 3D 示意。
5. IF 所选集装箱内没有已分配货物, THE System SHALL 展示空箱模型并提示该箱无已装货物。

### Requirement 7: 装箱任务管理

**User Story:** AS 装箱计划人员, I want 以任务为单位保存输入数据、规则启用状态与计算结果, so that 同一批货可以反复调整并对比方案。

#### Acceptance Criteria

1. THE System SHALL 允许用户创建装箱任务，任务包含名称、创建时间、输入数据、规则启用状态与最新计算结果。
2. WHEN 用户修改任务中的货物、集装箱或规则启用状态后重新计算, THE System SHALL 用新方案替换该任务的当前计算结果，并保留最近一次成功计算的方案供查看。
3. THE System SHALL 允许用户打开已有任务并继续编辑导入数据、规则与导出模板。

### Requirement 8: 包装类型可分柜与 PN 连续装箱

**User Story:** AS 装箱计划人员, I want 相同包装类型可以进不同柜子，同时让相同 PN 尽量连续装, so that 一类包装能分柜，而同一物料号在相邻柜子里接续装完。

#### Acceptance Criteria

1. WHEN 多件货物具有相同的非空包装类型, THE System SHALL 允许这些货物分配到不同的集装箱。
2. WHEN 多件货物具有相同的非空 PN, THE System SHALL 将这些货物按连续装箱处理：先在当前集装箱内尽量装满该 PN，装不下的剩余件数接着装入下一个集装箱。
3. THE System SHALL 使同一 PN 在同一集装箱内的已分配货物沿箱长方向连续放置。
4. THE System SHALL 使同一 PN 跨柜时占用相邻的集装箱序号，例如 40GP-1 未装完则在 40GP-2 继续该 PN，中间不插入其他 PN 的整段货物。
5. WHEN 货物的 PN 为空, THE System SHALL 不对该货物施加 PN 连续装箱约束。
6. IF 某件相同 PN 的货物在连续装箱后仍无法放入任何剩余集装箱, THE System SHALL 仅将该件标记为未分配，其余已连续装入的相同 PN 货物保持已分配。

### Requirement 9: 装卸方式与人工装箱重量上限

**User Story:** AS 装箱计划人员, I want 按叉车装箱与人工装箱区分作业, so that 超过人工可搬重量的货物只按叉车方式安排。

#### Acceptance Criteria

1. THE System SHALL 为每件货物记录装卸方式，取值仅为叉车装箱或人工装箱。
2. WHEN 货物重量大于 30 kg, THE System SHALL 将该货物的装卸方式视为叉车装箱。
3. WHEN 货物重量小于或等于 30 kg 且导入数据指定装卸方式为人工装箱, THE System SHALL 按人工装箱处理该货物。
4. WHEN 货物按叉车装箱处理, THE System SHALL 按铲齿长度约束校验该货物的进叉尺寸与放置深度。
5. THE System SHALL 允许将人工装箱重量上限作为可配置参数，默认值为 30 kg。

### Requirement 10: 轻货在上、重货在下

**User Story:** AS 装箱计划人员, I want 较重货物位于较轻货物下方, so that 堆叠后下层不被上层压坏且重心更稳。

#### Acceptance Criteria

1. WHEN 两件货物在同一集装箱内形成上下堆叠关系, THE System SHALL 保证下层货物单件重量大于或等于上层货物单件重量。
2. IF 某件货物无法找到满足轻重顺序的堆叠位置且无地面可用位置, THE System SHALL 将该货物标记为未分配，并给出原因为轻重堆叠约束不满足。
3. THE System SHALL 将直接放置在箱底的货物视为满足本规则。

### Requirement 11: 易压货物承压约束

**User Story:** AS 装箱计划人员, I want 标明不能被压的货物, so that 这类货物顶部不再堆放其他箱子。

#### Acceptance Criteria

1. WHEN 货物被标记为易压, THE System SHALL 禁止任何其他货物堆叠在该货物正上方。
2. THE System SHALL 允许易压货物堆叠在其他非易压货物之上，前提是同时满足轻重堆叠规则。
3. THE System SHALL 允许易压货物独占一层，即该层仅包含该货物或与其并排且互不上下堆叠的货物。
4. IF 易压货物无法获得无上压的位置, THE System SHALL 将该货物标记为未分配，并给出原因为易压约束不满足。

### Requirement 12: 同种堆叠约束

**User Story:** AS 装箱计划人员, I want 某些箱子只与同种货物上下堆叠, so that 不同品类不会互相叠压。

#### Acceptance Criteria

1. WHEN 货物被标记为仅同种堆叠, THE System SHALL 仅允许货物类型相同的货件作为该货物的直接上层或直接下层。
2. THE System SHALL 允许仅同种堆叠货物与其他类型货物在同一层并排放置。
3. WHEN 仅同种堆叠货物放置在箱底且其上方无货物, THE System SHALL 将该摆放视为满足本规则。
4. IF 仅同种堆叠货物无法获得同种上下邻接或独占堆叠位置, THE System SHALL 将该货物标记为未分配，并给出原因为同种堆叠约束不满足。

### Requirement 13: Site 同柜与隔离

**User Story:** AS 装箱计划人员, I want 按目的地决定哪些货必须放在一起、哪些货必须分开, so that 不同目的地的装卸顺序与混装限制得到遵守。

#### Acceptance Criteria

1. WHEN 用户在 Site 分组确认中将若干 Site 勾选为必须同柜, THE System SHALL 将这些 Site 下的货物视为同一同柜组，全部分配到同一个集装箱，并禁止拆到多个集装箱。
2. WHEN 用户在 Site 分组确认中将若干 Site 勾选为必须分离, THE System SHALL 将这些 Site 下的货物分配到不同的集装箱。
3. IF 必须同柜的 Site 组无法全部装入任何一个可用集装箱, THE System SHALL 将该组全部货物标记为未分配，并给出原因为同柜组无法整组入箱。
4. IF 必须分离的 Site 下货物被分到同一集装箱, THE System SHALL 拒绝该分配并重新选择集装箱；若无可用集装箱，THE System SHALL 将冲突货物标记为未分配，并给出原因为 Site 隔离约束不满足。
5. WHEN 用户未对任何 Site 勾选必须同柜或必须分离, THE System SHALL 不因 Site 施加同柜或隔离约束。

### Requirement 14: 规则冲突优先级

**User Story:** AS 装箱计划人员, I want 勾选并调整互斥规则的优先顺序, so that 规则冲突时按我指定的顺序取舍。

#### Acceptance Criteria

1. THE System SHALL 提供规则冲突优先级配置界面，列出可能互斥的装箱规则供用户勾选与排序。
2. THE System SHALL 将 Site 必须同柜约束的默认优先级置于最高，其后依次为 PN 连续装箱与 Site 必须分离。
3. WHEN 用户勾选规则并调整顺序后保存, THE System SHALL 在下一次计算中按该顺序处理互斥约束。
4. WHEN 两条已启用规则对同一批货物给出互斥要求, THE System SHALL 遵守优先级更高的规则，并在计算结果中记录被降级的规则名称。
5. IF 用户未保存自定义优先级, THE System SHALL 使用默认顺序：Site 必须同柜、PN 连续装箱、Site 必须分离、同种堆叠、易压、轻重堆叠、装卸方式。

### Requirement 15: 装箱结果 KPI

**User Story:** AS 装箱计划人员, I want 用一组明确指标衡量装箱方案, so that 可以比较不同算法与规则配置下的结果优劣。

#### Acceptance Criteria

1. WHEN 一次计算完成, THE System SHALL 为每个已使用集装箱及整个任务计算并展示下列 KPI：体积利用率、载重利用率、用箱数、装载完成率、未分配件数、未分配体积、未分配重量、作业便利性得分、约束满足率、重心纵向偏移、计算耗时。
2. THE System SHALL 按以下定义计算 KPI：
   - 体积利用率 = 已装货物体积之和 / 集装箱内部容积
   - 载重利用率 = 已装货物重量之和 / 集装箱最大载重
   - 用箱数 = 至少装入一件货物的集装箱数量
   - 装载完成率 = 已分配件数 / 待装总件数
   - 作业便利性得分 = 满足由内向外装载顺序的货件数 / 已分配件数
   - 约束满足率 = 未触发规则降级的已分配件数 / 已分配件数
   - 重心纵向偏移 = 已装货物合成重心沿箱长方向相对箱体几何中心的偏移量，单位为毫米
   - 计算耗时 = 本次算法从开始到产出方案的墙钟时间，单位为秒
3. THE System SHALL 在任务摘要、3D 示意旁侧栏及 Excel 导出中展示上述 KPI。
4. WHEN 用户同时运行多种算法, THE System SHALL 以对照表列出各算法的 KPI，并允许用户按任一 KPI 列排序。
5. THE System SHALL 将体积利用率、载重利用率、装载完成率、约束满足率、作业便利性得分以 0% 至 100% 的百分数展示，保留一位小数。

### Requirement 16: 多种主流装箱算法

**User Story:** AS 装箱计划人员, I want 在多种主流装箱算法中选择或对比, so that 能在利用率与作业便利性之间选出合适方案。

#### Acceptance Criteria

1. THE System SHALL 内置下列装箱算法，并在计算前供用户勾选：深底左填充（DBLF）、极点启发式（Extreme Point）、最大空腔（Empty Maximal Space）、砌墙法（Wall Building）、 Guillotine 切割。
2. WHEN 用户勾选一种算法并开始计算, THE System SHALL 仅用该算法生成一套装箱方案及对应 KPI。
3. WHEN 用户勾选多种算法并开始计算, THE System SHALL 对每种算法各生成一套方案，并以 KPI 对照表展示。
4. THE System SHALL 允许用户将对照表中的某一套方案设为当前任务的采用方案，供 3D 示意与 Excel 导出使用。
5. WHILE 任一算法生成方案, THE System SHALL 对每件已分配货物校验全部已启用的装箱规则，并遵守由内向外装载顺序与铲齿长度约束。
6. IF 某算法在可配置时限内未产出完整方案, THE System SHALL 返回该算法已得到的部分方案、KPI 及超时标记。
7. THE System SHALL 将算法计算时限作为可配置参数，默认值为 60 秒。

### Requirement 17: 由内向外的装载顺序

**User Story:** AS 现场装箱人员, I want 货物从箱子内部依次向外排列, so that 叉车和人工始终从箱门侧作业，避免后装货物被先装货物堵住。

#### Acceptance Criteria

1. THE System SHALL 为每件已分配货物生成装载序号，序号从 1 递增，序号越小越靠近箱内深处。
2. WHEN 两件货物位于同一集装箱, THE System SHALL 保证装载序号较小的货物其靠箱内深处的端面，比装载序号较大的货物更靠近或同样靠近箱内深处。
3. THE System SHALL 将满足本顺序的方案计为作业便利性得分的分子来源。
4. WHEN 用户查看装箱方案, THE System SHALL 按装载序号列出作业步骤，并在 3D 示意中支持按序号逐步显示已装货物。
5. IF 某件货物在遵守由内向外顺序后无法放入任何集装箱, THE System SHALL 将该货物标记为未分配，并给出原因为装载顺序约束不满足。

### Requirement 18: 铲齿长度约束

**User Story:** AS 现场装箱人员, I want 按叉车铲齿长度限制叉车货的尺寸与放置深度, so that 叉车能够插入并托稳货物后从箱门侧放入。

#### Acceptance Criteria

1. THE System SHALL 将铲齿长度作为可配置参数，默认值为 1220 mm。
2. WHEN 货物按叉车装箱处理, THE System SHALL 要求该货物在进叉方向上的边长小于或等于铲齿长度。
3. WHEN 货物按叉车装箱处理, THE System SHALL 要求放置该货物时，从箱门到该货物靠箱内深处端面的距离大于或等于该货物进叉方向边长，以便货叉完整插入。
4. WHEN 货物按人工装箱处理, THE System SHALL 不对该货物施加铲齿长度约束。
5. IF 叉车货物的进叉方向边长大于铲齿长度, THE System SHALL 在允许旋转的前提下尝试将另一条水平边作为进叉方向；若仍大于铲齿长度，THE System SHALL 将该货物标记为未分配，并给出原因为铲齿长度约束不满足。
6. THE System SHALL 在导入模板或任务参数中提供铲齿长度字段，缺省时使用默认值 1220 mm。

### Requirement 19: 固定箱型与自由组合求最优

**User Story:** AS 装箱计划人员, I want 在固定箱型和自由组合之间切换，并在自由组合中锁定箱型或数量, so that 既能按现有柜量装箱，也能在允许范围内求出更优用箱方案。

#### Acceptance Criteria

1. THE System SHALL 在计算前提供两种用箱模式：固定箱型模式、自由组合模式，用户必须选择其中一种。
2. WHEN 用户选择固定箱型模式, THE System SHALL 仅使用任务中已指定的箱型及各箱型数量生成方案，计算过程中不增加箱型、不减少箱型、不改变各箱型数量。
3. WHEN 用户选择自由组合模式且未设置箱型锁定与数量锁定, THE System SHALL 在系统箱型目录的全部箱型中搜索用箱组合，并按最优目标产出方案。
4. WHEN 用户在自由组合模式下勾选箱型锁定, THE System SHALL 仅使用被勾选的箱型参与搜索，未勾选的箱型使用数量为 0。
5. WHEN 用户在自由组合模式下对某一箱型设置数量锁定, THE System SHALL 使该箱型在结果中的使用数量等于锁定值。
6. THE System SHALL 允许在同一次自由组合计算中同时使用箱型锁定与数量锁定：先按箱型锁定限定可选箱型，再按数量锁定固定其中若干箱型的数量，其余已锁定箱型的数量由搜索决定。
7. THE System SHALL 将自由组合的最优目标定义为：首先最大化装载完成率，其次最小化用箱数，再次最大化全部已用箱的平均体积利用率。
8. WHEN 自由组合搜索完成, THE System SHALL 输出最优方案的箱型清单、各箱型数量及对应 KPI，并允许用户将该方案设为当前任务的采用方案。
9. IF 固定箱型模式下指定的箱型与数量无法装入全部货物, THE System SHALL 仍产出方案，将未能装入的货物标记为未分配，并给出原因为固定箱量不足。
10. IF 自由组合模式下箱型锁定与数量锁定导致无可行组合, THE System SHALL 终止该次搜索，并提示锁定条件无可行解。
11. THE System SHALL 从箱型库读取可用箱型供固定箱型模式与自由组合模式引用。
12. THE System SHALL 允许用户为自由组合设置各箱型的数量上限；未设置上限时，该箱型数量上限为可装入全部剩余货物所需的最小整数。

### Requirement 20: Web 应用形态

**User Story:** AS 装箱计划人员, I want 在浏览器中完成全部装箱工作, so that 界面与 3D 示意无需安装插件即可使用。

#### Acceptance Criteria

1. THE System SHALL 以 Web 应用形式提供全部功能，用户通过浏览器访问。
2. THE System SHALL 在浏览器中完成任务管理、箱型库维护、包装主数据维护、模板导入、规则配置、计算、KPI 对照、3D 示意与 Excel 导出。
3. THE System SHALL 在 3D 示意中使用浏览器内可旋转、平移、缩放的模型，无需安装插件。
4. THE System SHALL 在 Windows 上通过可执行文件启动本 Web 应用，详见 Requirement 24。

### Requirement 21: 箱型库维护

**User Story:** AS 规则管理员, I want 在专业箱型库中维护集装箱规格, so that 计算时引用的箱型尺寸与载重与现场实际柜型一致。

#### Acceptance Criteria

1. THE System SHALL 提供箱型库维护界面，列出全部箱型记录，支持按箱型代码、名称、启用状态筛选。
2. THE System SHALL 为每条箱型记录维护下列字段：箱型代码、名称、ISO 代码、内部长、内部宽、内部高、箱门宽、箱门高、最大载重、箱自重、内部容积、启用状态、备注。
3. THE System SHALL 在箱型库中预置至少 20GP、40GP、40HQ 三条启用记录，字段值为对应箱型的常用内部尺寸与最大载重。
4. WHEN 用户新建或编辑箱型, THE System SHALL 要求箱型代码在库内唯一，并要求内部长、内部宽、内部高、最大载重为正数。
5. WHEN 用户保存箱型, THE System SHALL 用内部长、内部宽、内部高自动计算内部容积，并允许用户覆盖该容积值。
6. WHEN 用户将某箱型设为停用, THE System SHALL 使该箱型不再出现在新任务的固定箱型选项与自由组合可选箱型中，已引用该箱型的既有任务仍可打开查看。
7. IF 用户删除已被任一任务引用的箱型, THE System SHALL 拒绝删除并提示改为停用。
8. THE System SHALL 允许用户复制已有箱型作为新建草稿，复制后的箱型代码需由用户改为唯一值后才能保存。
9. THE System SHALL 允许从箱型库导出当前列表为 Excel，并允许按箱型导入模板批量新增或更新箱型；更新时以箱型代码匹配已有记录。

### Requirement 22: 包装主数据与临时包装

**User Story:** AS 装箱计划人员, I want 预先定义常用包装，并在任务中导入仅本次有效的临时包装, so that 常规货用主数据、偶发货用临时规格，两种来源都能参与计算。

#### Acceptance Criteria

1. THE System SHALL 提供包装主数据维护界面，列出全部预定义包装，支持按包装代码、包装类型、货物类型、启用状态筛选。
2. THE System SHALL 为每条包装主数据维护下列字段：PN、包装代码、名称（PackMatls）、包装类型、货物类型、长、宽、高、箱重、净重、毛重、体积、是否可水平旋转、是否易压、是否仅同种堆叠、默认装卸方式、最大堆码层数、启用状态、备注。
3. WHEN 用户新建或编辑包装主数据, THE System SHALL 要求 PN 在已填写时于主数据内唯一，要求名称在已填写时可用于查找，并要求长、宽、高、单件重量为正数。
4. WHEN 用户将某包装主数据设为停用, THE System SHALL 使该包装不再出现在新任务的包装选择列表中，已引用该包装的既有任务仍可打开查看。
5. THE System SHALL 允许用户在任务中从包装主数据选择包装并填写件数与 Site 后加入待装清单。
6. THE System SHALL 允许用户在任务中导入临时包装：导入文件中的包装行写入当前任务，不写入包装主数据。
7. WHEN 导入行中的长、宽、高、体积、箱重、净重或毛重与包装主数据不一致, THE System SHALL 以导入表中已有值为准，不覆盖为主数据值。
8. WHEN 用户选择将临时包装提升为主数据, THE System SHALL 在包装代码不冲突时将该临时包装写入包装主数据；若代码冲突，THE System SHALL 要求用户更改代码或放弃提升。
9. THE System SHALL 在同一任务的待装清单中同时接受来自包装主数据的货物与临时包装货物，计算时对两类货物使用同一套装箱规则。
10. THE System SHALL 为临时包装提供与包装主数据相同的规格字段，并额外标记来源为临时，该标记随任务保存、出现在导入预览与 Excel 导出中。

### Requirement 23: 极简留白界面

**User Story:** AS 装箱计划人员, I want 页面采用极简留白风格, so that 核心内容和主要操作一眼可见，界面干净且有重点。

#### Acceptance Criteria

1. THE System SHALL 使用暖白作为页面背景色，使用深灰作为正文文字色。
2. THE System SHALL 在全站只使用一种强调色，该强调色仅用于主按钮、当前导航项、关键 KPI 数值与必要的焦点状态。
3. THE System SHALL 将页面主标题、区块标题、正文、辅助说明设置为至少四级字号，主标题明显大于区块标题，区块标题明显大于正文。
4. THE System SHALL 在同一视觉区域内使用统一的左对齐或网格对齐，卡片、表单标签、表格列与按钮组对齐到同一基准线。
5. THE System SHALL 在页面边缘、区块之间、标题与正文之间、表单字段之间保留明确留白，避免区块贴边或控件挤在一起。
6. THE System SHALL 将当前页的核心内容置于首屏主区域，并将该页唯一的主要操作做成强调色主按钮；同一操作区最多出现一个强调色主按钮。
7. THE System SHALL 将次要操作做成深灰描边或文字按钮，视觉权重低于主按钮。
8. THE System SHALL 限制装饰元素：无渐变背景、无多余描边色块、无多种彩色标签争抢视线；状态提示仅用深灰文字加一种强调色或中性灰区分。
9. THE System SHALL 在任务、箱型库、包装主数据、规则、计算结果、3D 示意、导出各页面统一应用本需求的背景、文字色、强调色、标题层级、对齐与留白规则。

### Requirement 24: Windows 可执行文件启动

**User Story:** AS 装箱计划人员, I want 在 Windows 电脑上双击一个可执行文件即可打开本工具, so that 现场电脑无需单独部署服务器或记忆访问地址。

#### Acceptance Criteria

1. THE System SHALL 提供可在 Windows 上运行的可执行文件作为启动程序。
2. WHEN 用户双击该可执行文件, THE System SHALL 在本机启动 Web 服务，并打开系统默认浏览器进入本应用。
3. THE System SHALL 将数据文件保存在本机，关闭可执行文件对应的进程后，再次启动仍能读取箱型库、包装主数据与已保存任务。
4. IF 本机约定端口已被占用, THE System SHALL 改用空闲端口启动，并在浏览器中打开实际地址。
5. WHEN 用户关闭启动程序, THE System SHALL 停止本机 Web 服务。
6. THE System SHALL 使该启动方式覆盖全部 Web 功能，与浏览器内操作范围一致。

### Requirement 25: 样表导入列映射与规格补全

**User Story:** AS 装箱计划人员, I want 按现有业务 Excel 直接导入，缺尺寸的行按 PN 或包装名称从主数据补全, so that 无需改表结构也能开算。

#### Acceptance Criteria

1. THE System SHALL 将导入表列按以下映射解析：A 箱号 No、B 长 Length、C 宽 width、D 高 high、E 体积 CBM、F OUTCASE NO.、G PackMatls、H 箱重/Tare weight、I 净重 NET WEIGHT、J 毛重 TOTAL WEIGHT、K PN、L 备注、M Site、N 集装箱号、O 关单号、P DN、Q 尺寸。
2. THE System SHALL 将长、宽、高的单位视为厘米，将箱重、净重、毛重的单位视为千克。
3. WHEN 导入行的长、宽、高均有值, THE System SHALL 使用该行表内尺寸与重量参与计算，即使包装主数据中存在不同数值。
4. WHEN 导入行缺少长、宽或高, THE System SHALL 先按 PN 查找包装主数据；PN 为空时再按 PackMatls 名称查找。
5. WHEN 按 PN 或 PackMatls 命中已启用的包装主数据, THE System SHALL 用主数据补全该行空缺的长、宽、高、体积、箱重、净重、毛重，表内已有字段保持不变。
6. IF 导入行缺少长、宽或高，且 PN 与 PackMatls 均无法命中已启用的包装主数据, THE System SHALL 在导入预览中标出该行，列出缺失的 PN 与 PackMatls，并阻止开始计算。
7. WHEN 存在缺失规格的行, THE System SHALL 提供批量维护：导出待填表（含 PN、PackMatls 及规格空列），允许用户填完后一次写入包装主数据，并支持在页面上逐条补全。
8. WHEN 用户完成批量或逐条维护后选择重新匹配, THE System SHALL 再次按 PN 优先、PackMatls 次之补全空缺行。
9. THE System SHALL 允许将有完整长宽高的导入行按 PackMatls 写入包装主数据，供后续按名称查找，例如 OUTCASE(IB-1)。
10. THE System SHALL 在导入时忽略 N 列（集装箱号）中的已有值，不把该列作为固定指派。

### Requirement 26: 运算前 Site 同柜与隔离确认

**User Story:** AS 装箱计划人员, I want 上传表格后、运算前勾选哪些 Site 必须同柜、哪些必须分离, so that Site 列只作为候选，最终约束由我确认。

#### Acceptance Criteria

1. WHEN 导入预览通过规格补全校验, THE System SHALL 进入 Site 分组确认，按 Site 列出该站点下的外箱号、PackMatls、体积与重量。
2. THE System SHALL 在 Site 分组确认中默认不勾选任何必须同柜或必须分离项。
3. WHEN 用户未勾选任何 Site 约束并开始计算, THE System SHALL 不因 Site 执行同柜或隔离规则。
4. THE System SHALL 允许用户将一个或多个 Site 勾选为必须同柜；被勾选的 Site 下全部货物构成一个同柜组，适用不可拆同柜规则。
5. THE System SHALL 允许用户将一个或多个 Site 勾选为必须分离；被勾选的 Site 彼此不得进入同一集装箱。
6. THE System SHALL 禁止将同一 Site 同时勾选为必须同柜与必须分离。
7. WHEN 用户保存 Site 勾选结果, THE System SHALL 将该结果随任务保存，并在下一次计算中使用，直至用户再次修改。

### Requirement 27: 结果回写集装箱号与每柜顺序号

**User Story:** AS 装箱计划人员, I want 计算结果写回原表结构的集装箱号列，并新增每柜重排的装箱顺序列, so that 现场按柜号和顺序装货。

#### Acceptance Criteria

1. WHEN 计算完成并导出或回写, THE System SHALL 用结果中的集装箱标识覆盖 N 列，格式为 `{箱型}-{该箱型序号}`，例如 40GP-1。
2. THE System SHALL 在导出表中新增「装箱顺序」列，位于原表最后一列之后。
3. THE System SHALL 为每个集装箱单独从 1 开始编排装箱顺序号，序号越小越靠近箱内深处，与由内向外装载顺序一致。
4. WHEN 某行货物未被分配到任何集装箱, THE System SHALL 将该行 N 列与装箱顺序列留空，并在未分配明细中给出原因。
5. THE System SHALL 保留原表 A 至 Q 列的输入值（N 列除外，N 列被结果覆盖），并将关单号、DN、备注随行带出。

### Requirement 28: 文件编码与乱码防护

**User Story:** AS 装箱计划人员, I want 导入与导出的文件在任何常见 Excel 中打开都无乱码, so that 模板下载、数据导入、结果导出全链路可靠。

#### Acceptance Criteria

1. THE System SHALL 以 `.xlsx`（OpenXML，内置 UTF-8）作为全部导入与导出的文件格式。
2. WHEN 系统提供 CSV 兜底导出或模板时, THE System SHALL 使用带 BOM 的 UTF-8 编码生成该文件。
3. THE System SHALL 在导入解析时自动识别 UTF-8、带 BOM 的 UTF-8、GBK 编码的文本文件。
4. THE System SHALL 在含中文表头、中文备注、中文字段值的全链路导入导出中保持内容一致，导出文件在简体中文 Windows 的 Excel 中打开无乱码。
5. THE System SHALL 在含中文字符的下载文件名场景下保持文件名正确显示。

### Requirement 29: 3D 多箱展示与回放控制

**User Story:** AS 现场装箱人员, I want 每个集装箱都能查看装箱效果、控制回放速度，且选中箱子后视图居中, so that 逐柜核对时看得清、看得快。

#### Acceptance Criteria

1. THE System SHALL 以箱列表或页签形式列出方案中的每个集装箱，选中任一箱即在该箱的 3D 视图中显示该箱的完整装箱效果。
2. THE System SHALL 在用户选中某个集装箱后，将该箱模型居中显示于工作区中央，并自动调整视角使该箱完整可见。
3. THE System SHALL 提供回放控制：开始、暂停、上一步、下一步，以及至少 0.5 倍、1 倍、2 倍、4 倍四档播放速度。
4. WHEN 用户调整播放速度, THE System SHALL 以所选速度连续播放装载过程，已装货物保留显示，未装货物半透明或隐藏。
5. THE System SHALL 在回放过程中显示当前步骤的装载序号及该件货物的标识、包装、作业方式。

### Requirement 30: KPI 单箱与整体双层计算

**User Story:** AS 装箱计划人员, I want KPI 同时按每个集装箱和整个任务两级给出，且整体口径明确, so that 汇总数据可直接用于对外报告。

#### Acceptance Criteria

1. THE System SHALL 按每个集装箱计算：体积利用率、载重利用率、装载件数、装载重量、作业便利性得分、约束满足率、重心纵向偏移。
2. THE System SHALL 按以下口径计算整体 KPI：体积利用率 = 全部已装货物体积之和 / 全部已用集装箱内部容积之和；载重利用率 = 全部已装毛重之和 / 全部已用集装箱最大载重之和；装载完成率 = 已分配件数 / 待装总件数；未分配件数、体积、重量 = 各箱未分配量求和。
3. THE System SHALL 将整体作业便利性得分与约束满足率按已分配件数加权汇总，整体计算耗时取全部算法各自动态记录的最大值。
4. THE System SHALL 使任一整体 KPI 与其单箱 KPI 之间满足公式可复算：由单箱数值按第 2、3 条口径能推导出整体数值。
5. IF 任务存在未分配货物, THE System SHALL 保持整体装载完成率、未分配量与未分配明细逐件对账一致。
6. THE System SHALL 在导出 Excel 的用箱摘要中同时给出每个集装箱的 KPI 与整体 KPI 两级数据。

### Requirement 31: 计算进度与预计等待时间

**User Story:** AS 装箱计划人员, I want 计算耗时较长时看到进度和预计剩余时间, so that 能判断等待是否正常而不是以为系统卡死。

#### Acceptance Criteria

1. WHEN 计算开始, THE System SHALL 立即显示计算进行中的状态，包含当前算法名称。
2. WHILE 计算进行且已耗时超过 3 秒, THE System SHALL 展示进度与预计剩余时间；进度按算法内部阶段（自由组合的枚举进度、已放置件数比例）计算。
3. WHEN 多个算法并行计算, THE System SHALL 分别显示每个算法的进度，并在每个算法完成后即时更新其 KPI 行。
4. IF 某算法超时, THE System SHALL 明确显示超时标记与已用时，后续方案照常展示该算法的部分结果。
5. WHEN 计算全部完成, THE System SHALL 展示总耗时与各算法耗时，并与 KPI 表中的计算耗时一致。

## Open Items

以下内容待用户后续提供后写入本文件对应需求：

- 叉车作业通道宽度及货叉间距
- 其余装箱约束（旋转允许轴向、间隙、左右配重等）
- 3D 示意的交互细节（剖视、爆炸图、按层查看等，如需要）
- 导出模板可选字段的完整清单
- 多用户与权限是否需要
- KPI 权重及自动推荐最优方案的规则（如需要）
- 自由组合是否纳入单箱成本或租柜成本作为最优目标（如需要）
- 箱型库是否预置 45HQ、20RF、40RF 等特种箱
