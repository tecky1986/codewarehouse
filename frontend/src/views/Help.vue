<script setup lang="ts">
</script>

<template>
  <div class="page">
    <div class="top">
      <div>
        <h1>使用说明</h1>
        <p class="sub">界面模块、参数配置与校验码含义说明。</p>
      </div>
    </div>

    <!-- ============ 界面总览 ============ -->
    <section class="sec">
      <h2>一、界面总览</h2>
      <p>
        本工具围绕「任务」组织工作流。顶部导航栏提供以下入口：
      </p>
      <table class="tbl">
        <thead>
          <tr><th>导航项</th><th>路径</th><th>用途</th></tr>
        </thead>
        <tbody>
          <tr><td>引导</td><td>/onboarding</td><td>首次使用向导，展示 5 步快速上手流程。</td></tr>
          <tr><td>任务</td><td>/tasks</td><td>创建和管理装箱任务，进入 4 步配置向导（导入 → Site → 规则 → 计算）。</td></tr>
          <tr><td>箱型</td><td>/container-types</td><td>管理集装箱型号库（20GP / 40GP / 40HQ），设置内尺寸、门尺寸、最大载重等。</td></tr>
          <tr><td>主数据</td><td>/packages</td><td>管理包装主数据（PN + PackMatls），维护货物尺寸、重量、堆叠属性。</td></tr>
          <tr><td>导出</td><td>/export-templates</td><td>管理导出 xlsx 模板的列字段、顺序、列宽与对齐。</td></tr>
          <tr><td>参数</td><td>/settings</td><td>设置全局参数（人工搬运上限、叉车铲齿长度、算法时限、货物间隙）。</td></tr>
          <tr><td>说明</td><td>/help</td><td>本页，界面与参数参考手册。</td></tr>
        </tbody>
      </table>
    </section>

    <!-- ============ 任务配置 4 步流程 ============ -->
    <section class="sec">
      <h2>二、任务配置流程</h2>
      <p>
        在「任务」页新建任务后，系统按 4 步向导推进，顶部步骤条显示当前进度：
      </p>
      <table class="tbl">
        <thead>
          <tr><th>步骤</th><th>页面</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>1</td><td>导入与箱型</td>
            <td>上传 xlsx 样表，设置箱型模式（固定 / 自由组合），补齐缺失规格。单 Site 数据自动跳过第 2 步。</td>
          </tr>
          <tr>
            <td>2</td><td>Site 确认</td>
            <td>按 Site 列出货，勾选「同柜」或「分离」，同柜与分离互斥。只有 1 个 Site（或未填）时本步自动完成。</td>
          </tr>
          <tr>
            <td>3</td><td>规则配置</td>
            <td>勾选启用的装箱规则并用 ↑↓ 调整优先级，保存后进入计算。</td>
          </tr>
          <tr>
            <td>4</td><td>计算与结果</td>
            <td>勾选参与对比的算法，点击「开始计算」。完成后在 KPI 对照中采用方案，查看 3D 视图与导出报表。</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ============ 导入与箱型 ============ -->
    <section class="sec">
      <h2>三、导入与箱型设置</h2>
      <h3>3.1 导入列说明</h3>
      <p>导入 xlsx 时按以下列识别（N 列忽略）：</p>
      <table class="tbl">
        <thead>
          <tr><th>列</th><th>字段</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr><td>A</td><td>编号</td><td>行序号，用于导出回引。</td></tr>
          <tr><td>B / C / D</td><td>长 / 宽 / 高 (cm)</td><td>货物外部尺寸，单位为 cm；导入后按 mm 处理。</td></tr>
          <tr><td>E</td><td>CBM</td><td>单件体积（m³），可与 B/C/D 交叉校验。</td></tr>
          <tr><td>F</td><td>OUTCASE</td><td>外箱编号，标识单件。</td></tr>
          <tr><td>G</td><td>PackMatls</td><td>包装材料 / 类型，与 PN 一起作为主数据匹配键。</td></tr>
          <tr><td>H / I / J</td><td>箱重 / 净重 / 毛重 (kg)</td><td>重量字段；毛重 = 箱重 + 净重，参与载重校验。</td></tr>
          <tr><td>K</td><td>PN</td><td>产品编号，与 PackMatls 组合匹配主数据。</td></tr>
          <tr><td>L</td><td>备注</td><td>自由文本，不影响计算。</td></tr>
          <tr><td>M</td><td>Site</td><td>站点，用于 Site 同柜 / 分离规则。</td></tr>
          <tr><td>N</td><td>箱号</td><td>导入时忽略。</td></tr>
          <tr><td>O / P / Q</td><td>REF / DN / 其他</td><td>附加信息，参与导出但不影响装箱。</td></tr>
        </tbody>
      </table>

      <h3>3.2 箱型模式</h3>
      <table class="tbl">
        <thead>
          <tr><th>模式</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>固定箱型</td>
            <td>选择一种箱型并填写数量上限；0 表示不设上限，按货量自动估算。</td>
          </tr>
          <tr>
            <td>自由组合</td>
            <td>勾选多种箱型参与搜索；可对某些箱型锁数量或设数量上限。启用后额外开放「自由组合」算法。</td>
          </tr>
        </tbody>
      </table>

      <h3>3.3 缺失规格补齐</h3>
      <p>
        缺失长宽高的行按 PN + PackMatls 匹配主数据。可下载待填表批量补全并写回主数据；
        也可在「未匹配主数据」区勾选键、填写规格后一键写入主数据并自动重新匹配。
      </p>
    </section>

    <!-- ============ Site 确认 ============ -->
    <section class="sec">
      <h2>四、Site 确认</h2>
      <p>按 Site 列出货，每个 Site 可勾选「同柜」或「分离」，两者互斥：</p>
      <table class="tbl">
        <thead>
          <tr><th>选项</th><th>效果</th></tr>
        </thead>
        <tbody>
          <tr><td>同柜</td><td>该 Site 的货物尽量装入同一集装箱。</td></tr>
          <tr><td>分离</td><td>该 Site 的货物尽量装入不同集装箱。</td></tr>
          <tr><td>未设</td><td>不施加 Site 约束。</td></tr>
        </tbody>
      </table>
      <p>数据只有 1 个 Site（或未填 Site）时，本步自动完成，可直接跳到规则配置。</p>
    </section>

    <!-- ============ 规则配置 ============ -->
    <section class="sec">
      <h2>五、规则配置</h2>
      <p>
        启用规则按优先级从高到低排列（P1 最高）。可用 ↑↓ 调整顺序，勾选启用。
        规则生效顺序 = 列表顺序，靠前的规则在冲突时优先满足。
      </p>
      <table class="tbl">
        <thead>
          <tr><th>规则</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr><td>Site 同柜</td><td>标记为「同柜」的 Site 货物尽量装入同一集装箱。</td></tr>
          <tr><td>Site 分离</td><td>标记为「分离」的 Site 货物尽量装入不同集装箱。</td></tr>
          <tr><td>PN 连续</td><td>同一 PN 的货物尽量连续放置，避免分散在不同箱内。</td></tr>
          <tr><td>同种堆叠</td><td>允许相同型号的货物上下堆叠。</td></tr>
          <tr>
            <td>堆码层数</td>
            <td>限制堆叠层数，取货物 max_stack（仅「同种堆叠」勾选时生效）；被压箱的每箱承重量（max_load）超限也违规。</td>
          </tr>
          <tr><td>轻重</td><td>重物在下、轻物在上，减少压损。</td></tr>
          <tr><td>装卸</td><td>考虑叉车装卸顺序，便于从门口依次取出。</td></tr>
        </tbody>
      </table>
    </section>

    <!-- ============ 全局参数 ============ -->
    <section class="sec">
      <h2>六、全局参数</h2>
      <p>全局参数对全部任务生效，在「参数」页修改后即时保存：</p>
      <table class="tbl">
        <thead>
          <tr><th>参数</th><th>单位</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>人工搬运上限</td><td>kg</td>
            <td>超过此重量的货物强制使用叉车装卸；默认 30 kg。</td>
          </tr>
          <tr>
            <td>叉车铲齿长度</td><td>mm</td>
            <td>叉车铲齿可插入货物底部的最大长度，用于判断货物是否可被叉车从指定方向取出；默认 1220 mm。</td>
          </tr>
          <tr>
            <td>算法计算时限</td><td>s</td>
            <td>单个算法的最长运行时间；超时后保留当前最优解并标记 timed_out；默认 60 s。</td>
          </tr>
          <tr>
            <td>货物间隙（左右 / 前后）</td><td>mm</td>
            <td>相邻货物在左右与前后方向的预留间隙；上下堆叠无间距，不受此值影响；默认 0 mm。</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ============ 包装主数据 ============ -->
    <section class="sec">
      <h2>七、包装主数据</h2>
      <p>主数据按 PN + PackMatls 双字段匹配，支持批量导入 Excel 和批量更新：</p>
      <table class="tbl">
        <thead>
          <tr><th>字段</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr><td>PN</td><td>产品编号，匹配键之一。</td></tr>
          <tr><td>PackMatls</td><td>包装材料 / 类型，匹配键之一。</td></tr>
          <tr><td>长 / 宽 / 高 (mm)</td><td>货物外部尺寸，单位为 mm。</td></tr>
          <tr><td>箱重 / 净重 / 毛重 (kg)</td><td>重量字段；毛重参与载重校验。</td></tr>
          <tr><td>四面进铲</td><td>勾选后货物四个侧面均可作为叉车进铲面。</td></tr>
          <tr><td>同种堆叠</td><td>勾选后允许相同货物上下堆叠，并启用「堆码层数」规则。</td></tr>
          <tr><td>最大堆码层数</td><td>勾选「同种堆叠」后生效；限制该货物最多堆叠的层数。</td></tr>
          <tr><td>每箱承重量 (kg)</td><td>该货物被压时能承受的最大重量；留空 = 不限，0 = 不可被压。</td></tr>
          <tr><td>默认装卸</td><td>叉车 / 人工，用于判断装卸方式；超过人工搬运上限的货物强制叉车。</td></tr>
          <tr><td>启用</td><td>停用后该条主数据不参与匹配与计算。</td></tr>
        </tbody>
      </table>
    </section>

    <!-- ============ 箱型库 ============ -->
    <section class="sec">
      <h2>八、箱型库</h2>
      <p>预置 20GP / 40GP / 40HQ，可新增自定义箱型。被任务引用后禁止删除：</p>
      <table class="tbl">
        <thead>
          <tr><th>字段</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr><td>代码 / 名称</td><td>箱型标识，如 20GP、40HQ。</td></tr>
          <tr><td>ISO 代码</td><td>ISO 标准箱型代码，如 22G1、45G1。</td></tr>
          <tr><td>内长 / 内宽 / 内高 (mm)</td><td>集装箱内部可用尺寸，决定可装载空间。</td></tr>
          <tr><td>门宽 / 门高 (mm)</td><td>柜门开口尺寸，货物无法通过柜门时报 E109。</td></tr>
          <tr><td>最大载重 (kg)</td><td>集装箱最大允许载重，参与载重利用率与超重校验。</td></tr>
          <tr><td>箱自重 (kg)</td><td>集装箱空箱重量，用于载重计算。</td></tr>
          <tr><td>单箱运费</td><td>导出报表中可选显示的费用字段。</td></tr>
          <tr><td>最大堆码层数</td><td>箱型级别的全局堆叠上限，与货物级 max_stack 取较小值生效。</td></tr>
        </tbody>
      </table>
    </section>

    <!-- ============ 算法与计算 ============ -->
    <section class="sec">
      <h2>九、算法与计算</h2>
      <p>任务详情页可勾选参与对比的算法，至少保留一个。计算完成后在 KPI 对照中比较并采用方案：</p>
      <table class="tbl">
        <thead>
          <tr><th>算法</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr><td>Bottom Left Back (DBLF)</td><td>经典角落启发式，按「最下、最左、最靠后」原则放置，速度快。</td></tr>
          <tr><td>最大空腔</td><td>在候选位置中选择最大空腔填充，空间利用率高。</td></tr>
          <tr><td>极点</td><td>基于极点搜索，适合不规则堆叠场景。</td></tr>
          <tr><td>分层装填</td><td>按层填充，砌墙 / 切割遵守行纪律。</td></tr>
          <tr><td>LNS 局部优化</td><td>大邻域搜索，在初始解上迭代优化。</td></tr>
          <tr><td>自由组合</td><td>仅在「自由组合」箱型模式下开放，跨箱型联合优化。</td></tr>
        </tbody>
      </table>

      <h3>KPI 指标说明</h3>
      <table class="tbl">
        <thead>
          <tr><th>指标</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr><td>用箱数</td><td>方案使用的集装箱数量。</td></tr>
          <tr><td>体积利用率</td><td>已装货物总体积 / 集装箱总容积。</td></tr>
          <tr><td>载重利用率</td><td>已装货物总毛重 / 集装箱最大载重。</td></tr>
          <tr><td>完成率</td><td>已分配货物件数 / 总件数，未分配件数越多完成率越低。</td></tr>
          <tr><td>约束满足</td><td>所有启用规则中满足比例，反映规则违反程度。</td></tr>
          <tr><td>校验</td><td>见下方「校验码说明」。</td></tr>
          <tr><td>未分配</td><td>因空间、载重或规则限制无法装入任何箱的货物件数。</td></tr>
          <tr><td>耗时</td><td>该算法运行时间（秒），受「算法计算时限」约束。</td></tr>
        </tbody>
      </table>
    </section>

    <!-- ============ 校验码 ============ -->
    <section class="sec">
      <h2>十、校验码说明</h2>
      <p>
        校验码在 KPI 对照的「校验」列显示。校验通过显示「通过」；未通过时列出
        出现的校验码及出现次数（如 <code>E102×3</code> 表示 E102 出现 3 次）。
        每个集装箱单独校验，方案级校验为所有箱的汇总。
      </p>
      <table class="tbl">
        <thead>
          <tr><th>校验码</th><th>含义</th></tr>
        </thead>
        <tbody>
          <tr><td class="code">E101</td><td>外侧货物阻挡内侧货物——外层箱遮蔽了内层箱的取货路径。</td></tr>
          <tr><td class="code">E102</td><td>当前排尚未完成——新的一排（row）在前一排未填满时即被开启；砌墙 / 切割算法遵守行纪律，DBLF / 最大空腔 / 极点算法可能出现此码。</td></tr>
          <tr><td class="code">E103</td><td>上层货物缺少支撑——悬空货物下方无承托。</td></tr>
          <tr><td class="code">E104</td><td>叉车进入路径被阻挡——叉车从门口（x=0）向内侧（x=inner_l）前进时，同 y 带内已有货物高出叉车工作高度，挡住了货叉。</td></tr>
          <tr><td class="code">E105</td><td>货物放置路径发生碰撞——放置过程中货叉与已有货物碰撞。</td></tr>
          <tr><td class="code">E106</td><td>货叉无法退出——卸货时货叉被相邻货物卡住，无法水平退出。</td></tr>
          <tr><td class="code">E107</td><td>叉车无法倒退出柜——卸货完成后叉车无法从柜内倒退出门。</td></tr>
          <tr><td class="code">E108</td><td>门架举升高度不足——货物顶部超过门架 / 门框高度，叉车无法举升到位。</td></tr>
          <tr><td class="code">E109</td><td>货物无法通过柜门——货物尺寸超过柜门开口（door_w / door_h）。</td></tr>
          <tr><td class="code">E110</td><td>货物超过下层承重——被压货物的每箱承重量（max_load）超限；max_load=0 表示不可被压。</td></tr>
          <tr><td class="code">E111</td><td>装载顺序存在循环依赖——A 压在 B 上，B 又压在 A 上，形成无法打破的循环。</td></tr>
          <tr><td class="code">E112</td><td>未预留叉车作业空间——货物布置导致叉车无法在柜内正常作业。</td></tr>
        </tbody>
      </table>

      <h3>反向卸货校验</h3>
      <p>
        校验器对每个方案执行「正向装载回放」和「反向卸货回放」两遍模拟。
        反向卸货按装载顺序倒序取出，检查货叉能否顺利退出（E106）和叉车能否倒退出柜（E107）。
        方案级 <code>unload_ok</code> 表示反向校验是否全部通过。
      </p>
    </section>

    <!-- ============ 导出 ============ -->
    <section class="sec">
      <h2>十一、导出</h2>
      <p>
        导出 xlsx / csv 报表，列字段由「导出模板」控制。默认模板包含：
        编号、长/宽/高(cm)、CBM、OUTCASE、PackMatls、箱重/净重/毛重(kg)、PN、备注、Site、
        箱号、装箱顺序、REF、DN、其他。
      </p>
      <p>
        在 KPI 对照页点击「导出 xlsx」或「CSV」按钮，导出当前采用方案。
        在「导出」页可新建 / 编辑模板，调整列字段、顺序、列宽与对齐；默认模板不可删除。
      </p>
    </section>

    <!-- ============ 箱型字段速查 ============ -->
    <section class="sec">
      <h2>十二、预置箱型参数速查</h2>
      <table class="tbl">
        <thead>
          <tr><th>箱型</th><th>ISO</th><th>内长 mm</th><th>内宽 mm</th><th>内高 mm</th><th>门宽 mm</th><th>门高 mm</th><th>最大载重 kg</th><th>箱自重 kg</th></tr>
        </thead>
        <tbody>
          <tr><td>20GP</td><td>22G1</td><td>5898</td><td>2352</td><td>2393</td><td>2340</td><td>2280</td><td>28200</td><td>2200</td></tr>
          <tr><td>40GP</td><td>42G1</td><td>12032</td><td>2352</td><td>2393</td><td>2340</td><td>2280</td><td>26700</td><td>3800</td></tr>
          <tr><td>40HQ</td><td>45G1</td><td>12032</td><td>2352</td><td>2698</td><td>2340</td><td>2585</td><td>26700</td><td>3900</td></tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.page {
  padding: 32px 40px 56px;
  max-width: 960px;
  margin: 0 auto;
}

.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

h1 {
  font-size: 22px;
  font-weight: 500;
  color: #2c2c2c;
  margin: 0;
}

.sub {
  font-size: 13px;
  color: #888;
  margin: 6px 0 0;
}

.sec {
  margin-bottom: 32px;
}

.sec h2 {
  font-size: 17px;
  font-weight: 500;
  color: #1a5c38;
  margin: 0 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e8e4e0;
}

.sec h3 {
  font-size: 14px;
  font-weight: 500;
  color: #444;
  margin: 16px 0 8px;
}

.sec p {
  font-size: 13px;
  color: #555;
  line-height: 1.7;
  margin: 0 0 10px;
}

code {
  background: #f0ede8;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  color: #1a5c38;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 12px;
}

.tbl th {
  text-align: left;
  font-size: 12px;
  color: #888;
  font-weight: 500;
  padding: 6px 10px;
  border-bottom: 1px solid #e8e4e0;
}

.tbl td {
  padding: 8px 10px;
  font-size: 13px;
  color: #333;
  border-bottom: 1px solid #f0ede8;
  vertical-align: top;
}

.tbl .code {
  font-family: monospace;
  font-size: 13px;
  font-weight: 600;
  color: #1a5c38;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .page {
    padding: 16px 16px 32px;
  }

  .top {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
