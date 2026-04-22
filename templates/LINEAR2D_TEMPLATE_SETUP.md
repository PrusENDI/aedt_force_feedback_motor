# Linearized2D 模板搭建手把手教程

这份文档是给你在 AEDT 里实际动手搭 `Linearized2D` 模板用的。

目标不是一步做到最精确，而是先做出一个：

1. 能稳定求解的 `Maxwell 2D` 模型
2. 能被当前工作区脚本反复改变量并调用的模板
3. 能导出固定命名报表的自动化入口

请把这份文档和下面两个文件一起看：

- `templates/TEMPLATE_CONTRACT.md`
- `CURRENT_SIM_REQUIREMENTS.md`

当前最重要的任务不是 3D，而是先把：

- `templates/linear2d_template.aedt`

做出来并跑通。

如果你已经手工建了一部分模型，不想从零按文档慢慢补，也可以直接运行下面这个脚本先帮你做“模板收口”：

- `scripts/bootstrap_linear2d_template.py`

这个脚本会自动处理：

- 尝试把活动设计收口到 `Linearized2D`
- 补齐 baseline 变量
- 补齐 helper 变量
- 尝试创建 `Setup_2D`
- 检查缺失的命名报表
- 把当前工程保存到标准模板路径
- 输出一份人工复核清单

如果 AEDT host 已经在运行，也可以从工作区外部直接排队执行：

- `.\launchers\Queue-BootstrapLinear2DTemplate.ps1`

收口之后，如果你想快速检查模板是否已经满足自动化要求，可以再运行下面这个复核脚本：

- `scripts/validate_linear2d_template.py`

这个脚本会检查：

- 当前设计名是否为 `Linearized2D`
- `Setup_2D` 是否存在
- 必需变量是否存在
- helper 变量是否存在
- 5 个必须报表是否存在
- 这些报表是否能导出 CSV
- 标准模板路径和备份路径是否存在

如果 AEDT host 已经在运行，也可以从工作区外部直接排队执行：

- `.\launchers\Queue-ValidateLinear2DTemplate.ps1`

如果你现在开始手工补报表和补 2D 模型，可以继续参考这两份更细的教程：

- `templates/AEDT_5_REPORTS_SETUP_GUIDE.md`
- `templates/AEDT_LINEAR2D_MODEL_BUILD_GUIDE.md`

## 1. 先理解这个 2D 模型的定位

这个 `Linearized2D` 不是最终真实的轴向磁通电机模型。

它是一个“线性展开的 2D 等效筛选模型”，主要用来比较不同参数方案之间的趋势，服务于粗筛。

你可以把它理解为：

- `2D`：便宜地筛方向
- `3D`：昂贵地做最终确认

所以这个模型当前最重要的不是“完全真实”，而是：

- 稳定
- 可参数化
- 可重复求解
- 可导出固定报表

## 2. 这个 2D 模型建议怎么理解

对你的轴向磁通电机，建议先采用“沿平均半径展开”的 2D 建模思路。

直观上就是：

- 把真实圆周方向，映射成 2D 模型里的水平周期方向
- 把平均半径处的极距，映射成 2D 切片长度
- 把磁钢、气隙、线圈、背铁，映射成一个可重复的极对切片

这一步只求“能筛选趋势”，不求直接替代 3D。

## 3. 开始前先确认三件事

1. AEDT 可以正常打开。
2. 当前工作区路径是：
   - `C:\weizijian\documents\motor\aedt_force_feedback_motor`
3. 你已经能在 AEDT 里运行 `Run PyAEDT Script`。

如果你已经看到下面这些文件在正常更新，说明 host 链路本身是通的：

- `runtime/heartbeat.json`
- `artifacts/host_session_probe.json`

## 4. 第一步：创建模板工程

请在 AEDT 中按下面顺序操作。

### 4.1 新建工程和设计

1. 打开 AEDT
2. 新建工程
3. 插入一个 `Maxwell 2D` 设计

### 4.2 把设计名改成固定值

设计名必须严格叫：

- `Linearized2D`

这个名字不能随意改。
因为当前脚本会按这个名字去找设计。

### 4.3 立即保存成模板文件

请直接保存到：

- `templates/linear2d_template.aedt`

完整路径就是：

- `C:\weizijian\documents\motor\aedt_force_feedback_motor\templates\linear2d_template.aedt`

建议你在开始建模前就先保存一次。

## 5. 第二步：先把必须变量建齐

当前脚本不会猜你的变量名，而是按固定变量名写入。

所以你必须先在 `Linearized2D` 设计里创建这些本地变量，而且名字必须完全一致。

### 5.1 必须变量列表

- `outer_diameter_mm`
- `inner_diameter_mm`
- `pole_count`
- `magnet_thickness_mm`
- `pole_arc_ratio`
- `airgap_mm`
- `backiron_thickness_mm`
- `coil_radial_span_mm`
- `coil_mean_radius_mm`
- `turns_per_phase`
- `conductor_width_mm`
- `conductor_thickness_mm`
- `parallel_strands`
- `phase_current_rms`
- `speed_rpm`
- `magnet_segments_per_pole`

### 5.2 建议直接填的初始值

第一版建议直接填这组 baseline：

- `outer_diameter_mm = 98mm`
- `inner_diameter_mm = 60mm`
- `pole_count = 24`
- `magnet_thickness_mm = 3.4mm`
- `pole_arc_ratio = 0.72`
- `airgap_mm = 0.7mm`
- `backiron_thickness_mm = 4.5mm`
- `coil_radial_span_mm = 12.5mm`
- `coil_mean_radius_mm = 39.5mm`
- `turns_per_phase = 66`
- `conductor_width_mm = 2.6mm`
- `conductor_thickness_mm = 0.6mm`
- `parallel_strands = 2`
- `phase_current_rms = 3A`
- `speed_rpm = 250rpm`
- `magnet_segments_per_pole = 1`

## 6. 第三步：再建一组辅助变量

这一组不是脚本强制要求，但非常建议建。

建议创建：

- `outer_radius_mm = outer_diameter_mm/2`
- `inner_radius_mm = inner_diameter_mm/2`
- `mean_radius_mm = coil_mean_radius_mm`
- `mean_diameter_mm = (outer_diameter_mm + inner_diameter_mm)/2`
- `pole_pitch_mm = pi*mean_diameter_mm/pole_count`
- `coil_inner_radius_mm = coil_mean_radius_mm - coil_radial_span_mm/2`
- `coil_outer_radius_mm = coil_mean_radius_mm + coil_radial_span_mm/2`

如果你希望展开切片更直观，也可以再加：

- `period_length_mm = 2*pole_pitch_mm`
- `magnet_arc_mm = pole_pitch_mm*pole_arc_ratio`

## 7. 第四步：第一版几何只画必要对象

第一版不要追求复杂。

建议至少画出下面 5 类区域：

- 磁钢区
- 气隙区
- 线圈或等效电流区
- 背铁区
- 外围空气区

第一版推荐：

- 几何尽量简单
- 先用矩形或分段矩形
- 外围空气区留得宽松一点

不要在第一版上来就做复杂磁钢分段、复杂端部等效或过细网格。

## 8. 第五步：确保变量真的驱动几何

这是最关键的一步。

不是“变量建好了”就够了，而是这些变量必须真的影响几何或激励。

至少确认下面这些变量改动后，模型会发生可见变化：

### 8.1 `magnet_thickness_mm`

改变后，磁钢厚度必须变化。

### 8.2 `airgap_mm`

改变后，气隙厚度必须变化。

### 8.3 `backiron_thickness_mm`

改变后，背铁厚度必须变化。

### 8.4 `coil_radial_span_mm`

改变后，线圈宽度必须变化。

### 8.5 `coil_mean_radius_mm`

改变后，线圈中心位置必须变化。

### 8.6 `pole_arc_ratio`

改变后，磁钢覆盖宽度必须变化。

如果变量只存在于变量表里，但几何完全没动，那么后面的扫参就没有意义。

## 9. 第六步：材料先从简单稳定开始

第一版建议这样处理。

### 9.1 磁钢

给磁钢区指定一个稳定可用的永磁材料。

第一版先别为了 `N48H` 和 `N50H` 的细节花太多时间。

### 9.2 线圈

给线圈区域指定铜或等效导体材料。

如果你这里用的是等效电流区域，也可以先优先保证激励关系是正确的。

### 9.3 背铁

给背铁指定一个常用钢材或等效电工钢。

第一版更关注它能否稳定给出 `Bmax_BackIron` 趋势。

### 9.4 外围区域

全部设为 `Air`。

## 10. 第七步：先把激励逻辑放进模板

当前脚本只会做三件事：

- 改变量
- 调求解
- 导出报表

所以模板里必须预先存在激励和报表逻辑。

### 10.1 带载 torque 工况

建议模板里已有一套通电状态，对应：

- `phase_current_rms = 3A`

后面脚本会改这个变量，但模板内部必须已经把它关联到绕组或等效电流。

### 10.2 cogging torque 工况

建议模板里已有零电流状态，或者零电流 torque 报表。

对应：

- `phase_current_rms = 0`

### 10.3 back-EMF 工况

建议模板里已有与 `speed_rpm` 关联的运动或反电势计算逻辑。

### 10.4 这一阶段的重点

你可以用不同 setup、不同 trace 或不同表达式来实现。

但对自动化来说，真正重要的是：

- 报表名固定
- 变量关系稳定
- 每次重开后仍然有效

## 11. 第八步：创建分析设置

你必须建一个 setup，而且名字必须严格叫：

- `Setup_2D`

第一版建议：

- 优先选择稳定设置
- 网格不要过细
- 先保证能反复跑通

因为当前工作流是“2D 粗筛、3D 确认”，所以这里不要一上来就做很重的求解设置。

## 12. 第九步：创建必须的 5 个报表

报表名称和变量名一样重要。

当前脚本会按固定名字去导出。
所以名字必须完全一致，大小写和下划线都不能变。

你必须创建下面这 5 个报表：

- `Torque_Loaded`
- `Torque_Cogging`
- `FluxLinkage_PhaseA`
- `BackEMF_LL`
- `Bmax_BackIron`

### 12.1 每个报表表示什么

#### `Torque_Loaded`

表示带载通电工况下的 torque 曲线。

#### `Torque_Cogging`

表示零电流下的 cogging torque 曲线。

#### `FluxLinkage_PhaseA`

表示 A 相磁链，或者一个等效 sanity check 曲线。

#### `BackEMF_LL`

表示线电压反电势曲线。

#### `Bmax_BackIron`

表示背铁最大磁密。

哪怕第一版只是一个比较粗的最大值曲线，也比没有要强。

## 13. 第十步：交给 agent 前必须手工验证

在第一次排队 `run_2d_screen` 前，请手工做完下面这些检查。

### 13.1 检查变量是否真的影响模型

手工改动一次：

- `magnet_thickness_mm`
- `airgap_mm`
- `backiron_thickness_mm`
- `coil_radial_span_mm`
- `coil_mean_radius_mm`

确认几何真的在变化。

### 13.2 检查 setup 是否能跑通

手工运行一次：

- `Setup_2D`

确认至少能求解成功一次。

### 13.3 检查 5 个报表是否能导出

逐个确认：

- 报表存在
- 报表能刷新
- 报表能导出 CSV

### 13.4 检查保存重开后是否仍然有效

请务必做一次：

1. 保存
2. 关闭工程
3. 重新打开工程
4. 再跑一次求解
5. 再导出一次报表

很多模板是在当前 GUI 会话里“看起来能用”，但重开就坏。

## 14. 第一轮最推荐的 smoke test 参数

建议第一次手工测试就用下面这组值：

- `outer_diameter_mm = 98`
- `inner_diameter_mm = 60`
- `pole_count = 24`
- `magnet_thickness_mm = 3.4`
- `pole_arc_ratio = 0.72`
- `airgap_mm = 0.7`
- `backiron_thickness_mm = 4.5`
- `coil_radial_span_mm = 12.5`
- `coil_mean_radius_mm = 39.5`
- `turns_per_phase = 66`
- `conductor_width_mm = 2.6`
- `conductor_thickness_mm = 0.6`
- `parallel_strands = 2`
- `phase_current_rms = 3`
- `speed_rpm = 250`
- `magnet_segments_per_pole = 1`

这组值和当前工作区默认 baseline 一致。

## 15. 模板准备好后，agent 会怎么用它

当 `templates/linear2d_template.aedt` 准备好以后，队列里的 `run_2d_screen` 会做这些事：

1. 读取搜索空间
2. 生成或读取 `cases/screening_2d.csv`
3. 先做 case 合法性检查
4. 把非法 case 写到：
   - `reports/2d_screening_invalid_cases.csv`
5. 把模板复制到：
   - `aedt_projects/linear2d_working.aedt`
6. 逐个 case 改变量
7. 逐个 case 求解
8. 逐个 case 导出 CSV 到：
   - `exports/2d/<case_id>/`
9. 汇总输出：
   - `reports/2d_screening_summary.csv`
   - `reports/2d_screening_ranked.csv`
   - `reports/2d_screening_failures.csv`
10. 写进度摘要：
   - `reports/2d_screening_progress.md`
   - `artifacts/linear_2d_progress.json`
11. 写模板预检结果：
   - `artifacts/linear_2d_preflight.json`
12. 生成 3D shortlist：
   - `cases/validation_3d.csv`

## 16. 第一轮最常见的错误

### 16.1 设计名不对

必须是：

- `Linearized2D`

### 16.2 setup 名不对

必须是：

- `Setup_2D`

### 16.3 报表名不对

必须严格一致：

- `Torque_Loaded`
- `Torque_Cogging`
- `FluxLinkage_PhaseA`
- `BackEMF_LL`
- `Bmax_BackIron`

### 16.4 变量存在，但没有驱动几何

这是最常见的问题之一。

### 16.5 报表能看，但导不出 CSV

自动化依赖的是报表导出，不是肉眼看到曲线。

### 16.6 模板重开后失效

这个也非常常见。
所以一定要做一次保存、关闭、重开、再求解。

## 17. 推荐你接下来的操作顺序

最推荐的顺序不是立刻去做 3D，而是：

1. 完成 `linear2d_template.aedt`
2. 手工跑通一次 `Setup_2D`
3. 手工确认 5 个报表都能导出
4. 启动 AEDT host
5. 从工作区外部执行：
   - `.\launchers\Queue-2DScreening.ps1`
6. 检查输出是否完整
7. 等 2D 粗筛跑通后，再开始做 `sector3d_template.aedt`

## 18. 如果你想最快跑通第一版

那就先满足下面这 4 条最低标准：

- 一个能求解的 `Linearized2D`
- 一个会随变量变化的简化几何
- 一个 `Setup_2D`
- 五个名字正确且能导出 CSV 的报表

只要这四件事齐了，就已经可以开始第一轮 agent 托管粗筛。

## 19. 你完成后怎么告诉我

你做完以后，最方便的反馈方式是这三种之一：

1. 告诉我：`linear2d_template.aedt` 已建好，5 个报表也建好了
2. 告诉我：你卡在哪一步，比如“报表不会建”或“电流激励不会关联变量”
3. 把你当前模板结构截图发我，我继续帮你逐步对照检查

如果你愿意，我下一步可以继续直接写：

- `SECTOR3D_TEMPLATE_SETUP.md`

或者更实用一点，我也可以继续给你写一份：

- “在 AEDT 里如何一步步创建这 5 个报表”的单独教程
