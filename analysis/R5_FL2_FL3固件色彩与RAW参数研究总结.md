# R5 4.29 自定义滤镜、色彩参数与网格生命周期研究

更新：2026-10-27。本文件为唯一研究总结。以下首先给出当前实现、纠错及验收状态；后面的旧版本章节为带时间的历史记录，不能据其“当前”“未加入”等措辞判断4.29。原始采集、历史源码和测试回执不改写。

## 4.29：自定义菜单右侧全称与输入隔离（2026-10-27）

用户报告4.28自定义页右侧没有全称，残留参数栏只能变为+1/−1；原厂创意外观里的组件正常。这纠正了把428回退离线通过视作右侧布局已验收的解读。428保留425错误MID getter和旧布局ABI：真实菜单属性PID3b2与行属性PID3b7不能混用；原生调整控件也不能作为自定义名称页的可交互组件。没有本轮机身RAM/崩溃栈，不能把静态缺陷称为唯一实机触发原因。

429保留428“无更新操作”要求，合入427按M4查明的真实MID、VT+40布局/原VT+30 query、首帧0和专用对象生命周期修正。私有白名单只创建实时取景壳、名称和左侧触摸区域；右侧仅全称，原生调整/箭头/footer及旧更新入口均不创建。上下/长按只切换配置；当前及关闭/MID变化后的私有输入不进原Look setter，原厂创意外观代码及原D9样式保持。选择按CP确认、原厂E4返回、再次CP确认、持久保存/发布、真实父值核对后退出；旧表“先保存再SELECT”只代表425之前顺序。

名称getter/UTF8桥接覆盖关闭及12项，连续/长按/稀疏配置、真实原生Enter、控件allocator、构造析构和manager/query通过。AP `74a8923e208790d4794a4790e9d8abf8c324795529ef6bcbc544b48af4728315`，RX61624/BSS136368，native arena42752；CP仍精确继承423，BIN v4、Gamma尾部和422网格生命周期不改。20回执、15项门控、最终DAT签名/CRC/篡改拒绝及751577088明文字节/736841块独立对照通过；DAT SHA256 `5d3f92fd5a6a8f71d542f281a546762e72a0bf7c971540600a41782ac89dcb8d`，754525608字节/BCD2904。

交付：`research/r5_custom_lut/build_r5_4.29_name_only_20261027/BODYDATA.DAT`；源码及证据：`analysis/r5_custom_menu429_20261027/README.md`。物理LCD/触摸/字体/透明度、三页RW实际装载、冷启动及ISP/JPG仍待机身验收；没有相机、Web或GitHub操作。旧版本、原始采集、首次镜像和历史回执保持。

## 4.28：按用户要求回退4.25并移除更新操作（2026-10-24）

当时交付改为4.28。以最终4.25 sync_exit为菜单基线，先重建精确复现AP11cd8005，再仅删除更新按钮、触摸入口、更新焦点/导航及手动刷新提交分支。页面不再引用reload_request；共享底层worker和自动开机/媒体导入保持。保留425选择同步应用、持久保存、父级选中值核对后退出及失败留页；BIN v4、CC1/block13/129点Gamma及422网格生命周期不改。

这次是用户指定回退，未纳入426/427菜单改动，425旧MID getter、pvt[8]布局接管及动态对象行为随基线保留。历史ABI调查和实机反馈仍保留，不能把回退写成对427修复方案的验收，也不能声称4.28已实机验证。

完整包754525608字节，BCD2804，DAT SHA256 `dd64c0d26cf71d3b595dcf20cf11d39abdff8f78eadd7241a833182d28e03816`；AP `85c0f93da51276c89419b6fd7415bbe41589045fd7fe79a4bf81c3aa1d0987da`，RX61784/BSS112536，原AP文件长度不变；CP精确保持423的8b38e753。页面22项、worker11项、原请求76项、wrapper10项、跨核28次选择通过；SD162项按完整闭包身份继承。13份必需回执、6检查、384冻结输入和13项SUMS，最终实际DAT独立签名/CRC/篡改拒绝、AP/CP提取和751577088明文字节/736841块逐字校验通过。

源码及限制：`analysis/r5_custom_menu428_rollback425_20261024/README.md`；最终回执：`analysis/r5_custom_menu428_rollback425_20261024/release_tests/delivery_verified.json`；包：`research/r5_custom_lut/build_r5_4.28_rollback425_20261024/BODYDATA.DAT`。未操作相机、SD或GitHub，实际LCD、冷启动及拍照仍待验收。以下427及更早章节保留历史。

## 2026-10-24配套发布：实拍v2、反推工作台与富士模拟滤镜

当前色彩工作台新任务默认`r5-paired-20261024-v2`，原始模型SHA256 `8879499fbd9b24899dcbd8fee4135b806fdcba1fd18a677b090b7af212b85a45`，11对实拍，refined-smooth-s3-a3，训练颜色覆盖42/256、留出RMSE3.696（8位RGB）。训练、压缩、整数选优及RAW预览共用PairedModel，历史模型身份继续读取。旧章节“默认暂定模型”“仅A7C2代理”“尚未接入”等表述只代表当时状态。新旧采集误差不能直接比较；未覆盖颜色属于外推，仍不能声称唯一恢复原厂ISP或跨条件验收。

独立`R5GridCalibrator/`支持上传BIN v4选配置、生成12探针、按文件名自然排序上传拍摄文件夹训练，支持Sony MPF/MPO主帧；多起点、颜色分层采样及坐标/响应交替优化。分享包不含workspace和私人照片。`R5ColorLab/`同步默认v2；合成ARW色卡在公开副本无损gzip保存，下载时还原并保持原散列，避免GitHub单文件限制。

富士九款模拟滤镜使用该v2模型重新训练压缩：AS/ASTIA、CC/CLASSIC CHROME、EBB/ETERNA BLEACH BYPASS、ET/ETERNA、NC/CLASSIC Neg.、NH/PRO Neg. Hi、PV/PROVIA、RA/REALA ACE、VN/Velvia。BIN v4为22196字节，SHA256 `5700b9dd8c1390ac851528f01be1776034d6b8fb66287cfffb3600351af38a93`，会完整替换配置集；各740留出色块RMSE7.740–11.044，非富士官方产品，机内颜色未验收。公开成品位于`filters/FUJ_grid_v2/`，原始交付位于`exports/FUJ_filters_grid_v2_20261024/`。

配套发布检查：反推器10项、响应模型3项、独立数据自检、10000颜色非零网格预测对照和零表恒等、原BIN逐字节及合成ARW下载回读通过。固件保持4.28原交付，不因发布整理重新修改。公开仓库缺少原机/签名输入，完整固件放v4.28 Release附件；原始镜像、密钥、私人照片和运行记录不发布。

## 4.27：M4接入复核与4.26重启反馈（2026-10-24）

用户最新明确确认4.25进入菜单正常，4.26点击自定义菜单触发重启，要求按M4接入制作4.27。4.25进入正常与其MID/ROW离线反例分别记录，不能用反例否认用户反馈。4.26实机菜单验收失败，后文旧“实体待验收”应按时间读取。

必须撤回“真正relayout在VT+30”的旧结论。R5 presenter原表header+10为addresspoint：数组pvt[8]即VT+30是边界查询，pvt[10]即VT+40才是layout setter。M4原0802.c覆盖[10]。冻结426真实manager1ec4908调用+40后会进入原1d0a970，重新创建原厂34控件并执行220844c；真实query consumer调用错误+30会把函数地址写成layout。旧测试和错误实现共用+30假设，未覆盖真实manager。这是已证实ABI缺陷，但未捕获机身重启PC，不能单独声称唯一直接原因。

4.27恢复原query、正确接管+40；first update按M4传0；区分对象所有权与可交互状态，关闭/MID变化后输入不进原Look setter、原生系统生命周期仍保留。原D9/父2d7工厂共享池，因此改用专用静态对象池、完整原ctor及原生清理，避免进入时堆分配失败被manager直接解引用，不能机械套用M4对象池覆盖父页。真实完整controller ctor/dtor、两个helper、真实manager与query双地址回放均通过；首次update第二参数写param+2d模式字节，0不是跳过绘制。低层UX/字体和真实GUI时序仍需实机反馈。

真实helper无边界越界；34节点静态arena需求45184B，小于原生最小池131072B。原native owner销毁后清指针，尚未发现double-free证据。未将这些未证实方向列为重启根因。

427构建与最终门控位于`analysis/r5_custom_menu427_20261024/`，旧版反例及M4对照在`analysis/r5_custom_menu427_crash_20261024/`。顶部更新、右侧仅名称、选择/更新同步提交与父值核对后退出保持；CP精确继承423、422网格生命周期及BIN v4不改。固件包身份以最终交付回执为准；本轮仅本地文件，无设备/GitHub操作。

## 版本与验收状态（4.29见前节，以下为历史）

当前本地交付4.27：754525608字节，BCD2704，DAT SHA256 `38806225e92b82514634283ef856a52fb5c1cf74a088c680c624accf5641116c`；AP `44aaa92ce274de716e93f0d235f5afe869cdd73c9c236b69564d2ea60cd789a8`。专用静态对象令BSS136376字节、RX62040字节，文件长度不增，RW无段重叠；未实测设备loader。18回执、13检查、390源输入与13项SUMS独立重核，最终实际DAT签名/CRC/篡改拒绝、AP/CP提取及751577088明文字节/736841块逐字对照通过。CP精确保持423的8b38e753，422网格生命周期不改。独立交付检查使用`verify_delivery427_final.py`，其自身散列绑定于`release_tests/delivery_verified.json`；冻结初版检查脚本曾保留0x26版本断言而拒绝2704，已另留说明，DAT未因此变化。没有机身/GitHub操作，实际进入、字体/LCD与成像等待用户验收。

以下4.26及更早交付为历史：

历史4.26菜单修正版：754,525,608字节，BCD `2604`，SHA256 `93d39f40071f1fcf69a2fbeabb051c9ddf9a71679f04aabdd56280bdc1f921ec`；AP `b44ebcdbf2fff8376c8c4dc3c21177cc87d3e74460fe19541832e4539f06f353`。15份必需回执/148输入绑定，修正菜单MID/ROW混用，移除自定义页右侧原生调整控件。完整包校验以 `analysis/r5_custom_menu426_20261024/release_tests/delivery_verified.json` 为准；实体字体/LCD与成像待验收，没有设备或GitHub操作。4.25用户已反馈按钮缺失及右侧异常，后文离线通过不代表实机通过。

历史4.25最终sync_exit交付：754,525,608字节，BCD `2504`，SHA256 `7dc3c3abf6f27e700b6e140de5e80af10bcf80867ef44ede2367e1928e264fb6`；AP `11cd80055a7781eee61663dbc9ef0a8fff74fdeeeb9a6c3a59b8a7de379ac95c`，CP精确继承4.23。选择和手动更新均经同步提交、保存与父值校验后退出。26项页面及固定11份回执门控通过；最终DAT签名/CRC/篡改拒绝、AP/CP独立提取和751,577,088明文字节逐字验证通过。尚未实机验收，本次不推送GitHub。前一sync_menu版的手动更新留页方案已按用户最新要求接续为sync_exit，旧包、源码保持。

以下4.24交付记录为历史及GitHub现状：

4.24在4.23独立自定义滤镜方案上修复真实主列表的第二路菜单ID转换，CP逐字节继承4.23。完整包754,525,608字节，BCD `2404`，SHA256 `01bf5ab58609b51d78803faefd352d6f85872b4dc67b7f738159af38e198e86a`。AP `a4c036eb4101820165748ca9819dd5afc803d11dc48f8b5eba3c9775f0c7995b`；CP `8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d`。

| 证据层 | 已知状态 |
|---|---|
| 历史实机基线 | 用户确认4.18实机结果没问题；不代表后来网格/菜单通过 |
| 4.21实机 | 开启实时取景显示设置后FL2网格屏幕可见，SD直出JPG与对照无该效果；拍摄网格未通过 |
| 4.23实机 | 用户报告新增菜单有占位、无名称且无法选中；早期子页测试不足以覆盖真实主列表 |
| 4.24主机验证 | 真实主列表/标题生产链、进入/选择/返回回放，包签名、CRC、完整独立解密通过 |
| 4.24实机 | 尚未取得安装、LCD菜单、冷启动保持、预览及JPG验收；不能写成已解决实机成像 |

GitHub以main发布源码和Web，完整DAT单独放在[v4.24候选Release](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware/releases/tag/v4.24)。公开源码缺少原厂镜像、密钥和部分本地依赖，不是可在干净仓库一键重建/刷任意机身的工具。首次备份、首次采集和签名私钥继续本地保护；本轮没有设备操作。

## 4.26：菜单身份纠错与右侧调整移除（2026-10-24）

用户反馈4.25自定义菜单没有“更新滤镜”，且右侧参数调整异常。该反馈纠正了先前仅靠控件声明及简化页面fixture即可判断入口/按钮完整的结论。没有取得此次机身AP回读；以下根因由冻结本地425及新426实际指令对照建立，不能据此声称本地散列就是机身安装散列。

4.25私有controller/presenter的mid()错误调用`0x28a87e8`，这是行属性PID`0x3b7`的地址；实际菜单MID由`0x28a8720`指向PID`0x3b2`。真实主菜单Enter写后者，行属性仍可为`0x1607`。旧页面fixture把错误getter直接返回635，掩盖了factory误回退原厂D9的路径。4.26改用真实菜单属性：菜单635/行1607进入私有页，原厂菜单/行635仍走原厂；冻结425在这两组输入下行为相反。此差异能解释按钮缺失及出现原厂右侧调整区。

自定义页另外改为明确控件白名单：仅保留实时取景壳、自定义文字及其触摸入口，排除原生右侧bitmap、箭头、footer/help和CloseScreen等控件；不再投影原生footer参数。右侧保留滤镜全称，原生调整操作不会进入原厂Look setter。原厂“创意外观”页面本身保持。原资源names/offset表只是节点名称，原生create_screen按style.w0分派类型；这不是“没有同步资源类型表”导致按钮消失。

新增原指令验证：真实菜单/行getter和425→426工厂对照，真实1004 Enter→MID写入→D9入队→实际factory表到私有分配gate；原生`view::create_screen`执行type/mask分派、names偏移和param map/style初始化，再以该map执行编译project及更新文字UTF8桥接。低层Widget/param分配、字体及UX后端仍是fixture，实体LCD、触摸命中与完整GUI调度待验收。旧425记录保留，不能把其26项fixture通过当作物理菜单已通过。

426只改变私有UI，worker/SD导入源码、代码常量及BSS地址逐项继承最终425；CP逐字节继承423，422整套网格/颜色生命周期保持。手动更新仍等待所有配置传输封存和当前选择应用保存；真实父菜单选中值核对成功才退出。失败留页；超时持有原sequence，不自动发新请求。同步边界仍为控制面及原厂提交，不新增LCD/ISP/JPG完成证明。实现与最终回执见`analysis/r5_custom_menu426_20261024/`。

## 4.25透明菜单与同步提交（2026-10-24）

本次按用户给定M4方法，改用R5原生D9创意外观页面壳，保留背景参数但不创建Background2 Widget。mask0意味着创建真实控件，不能解释为透明；物理LCD透明度、字体及刷新节奏仍待机身确认。左侧最多7行滚动简写，右侧全称，顶部“更新滤镜”，仅MID635走私有页面，原厂创意外观工厂、名称及私有颜色处理保持。

4.23／4.24原行为是先关闭页面、后台先保存再发送SELECT。4.25改为单worker串行事务：准确CP SELECT ACK、本次私有原厂E4执行体返回、下一序号CP SELECT ACK、原子保存、发布selected与成功。UI等待同一sequence；成功后调用真实父页更新链 `1d90de8→1bc4190→1bc3f64→1bd55fc→1bc8eb8→1bc50ec→descriptor getter`，并核对真实5B参数值已等于当前简写资源，才pop。失败、父值不符不退出；20秒仍未完成则保留pending、禁重复提交和返回，下一次操作只查询同一事务。

“更新滤镜”由同一worker重新读SD根目录R5NATIVE.BIN，沿用v4完整校验、全量替换/清空、原子机内保存、整套CP封存与名称发布。所有配置完成封存/加载且当前选择应用成功后，核对父值再退出；没有/损坏文件失败并保留旧配置；合法空BIN/零字节明确清空，移除当前选择后转关闭。私有页面对象独立OSAL分配并成对析构，避免D9与父1004的原生同index池覆盖。CP逐字节继承4.23，4.22网格恢复/不可变代际、CC1/block13/129点Gamma及实际原厂base尾部不改。

本版“同步”证据边界必须收窄：E4的九条native发送本身异步；E4返回加精确CP状态再确认不能独立证明FIFO/下游ISP完成或LCD新帧已显示。UI线程ID3与E4线程ID4独立；UI loop锁及前置model-snapshot guard已核对分发前释放，但不是全局所有锁的证明。实体媒体延迟、heap/cache、冷启动、预览和JPG仍需机身验收。

最终修订离线覆盖页面26项（含手动更新成功退出/失败留页/父值失败/超时后完成）、worker11项、原生请求链76项、包装器10项、主菜单六组/标题16项、跨核28次选择。SD162项实际执行AP448c4416，最终AP11cd8005的相关机器码、BSS地址、源/编译选项和原生入口逐项等同，显式继承测试而非冒称最终AP又运行162项。11份固定回执和包内签名/CRC/逐字独立解密由发布门控绑定。实现及边界见 `analysis/r5_custom_menu425_refresh_exit_20261024/README.md`；本次只本地交付，无相机或GitHub操作。

## 需要撤回或收窄的旧结论

| 旧结论/误解 | 当前修正与依据 |
|---|---|
| 子页能显示、模型回放通过即菜单入口完整 | 4.23遗漏第二菜单ID转换，真实列表将635变为CA4；4.24补实际生产者链的正反对照 |
| 描述符byte12是网格enable | 真enable为byte0；byte12为强度。旧字段解释作废 |
| 上传计数或函数返回成功等于JPG已应用 | 旧计数漏复制通路；软件交付、最终enable/submit、ISP接受和照片像素须分别验证 |
| 清配置或恢复原厂指针即可撤销硬件网格 | 旧硬件表可能残留；要从实际原厂RAM源重建不可变packed表并交付 |
| 已覆盖index3或root+3就能标为预览/JPG路径 | index3原厂仅条件支持；此前漏non-direct组合。root+3不能单独映射为预览/JPG，缺本次快门状态 |
| 1215字节是预览简略矩阵，原厂1620字节更精细 | 同为405节点×3通道；1215有符号字节系数打包为405个32位word，共1620字节，节点未缩减 |
| ST亮度差已锁定独有YGain/Knee | ST/NT共享引用；PT还有有条件局部表/寄存器路径。实际值和屏幕消费者未获，未锁定唯一根因 |
| 覆盖CC1/block13/Gamma即消除原厂滤镜的所有差异 | 仍保留Gamma尾60字节、YGain/Knee引用及原厂私有处理；基底外观仍影响结果 |
| PC网格数学就是R5 ISP数学 | 默认BT.601/固定响应为暂定模型；QAQ实测是A7C2跨机型代理，二者均非R5标定 |
| 旧BIN合并导入/旧网格开关仍适用 | 当前只接受v4，完整替换，所有配置必须带网格；不再兼容v2/v3或单独网格开关 |

此前“已完成”“全路径”等表述只在其具体离线回放范围内成立。原厂源并发复制、整帧参数原子切换、设备heap/cache及最终像素不由模拟或验签推出。

## 4.23／4.24菜单历史：独立选择原厂基底和自定义配置

原“创意外观”继续决定ST/PT/FL2等原厂基底；同级“自定义滤镜”MID `0x635` 单独选择关闭或配置1–12。左侧简写，右侧全称；名称只在自定义菜单使用，不覆盖原厂创意外观名称。按确认直接入队并走原生关闭返回，无额外保存按钮；工作器完成持久保存、SELECT及匹配ACK后才更新getter/刷新，不能说UI点击等于同步落盘成功。

4.23真实可见列表生产者 `0x1BD9B9C` 经facade+0x748调用 `0x1BD2020`。原1589项键0…1588不含新MID1589，回退CA4，导致占位无标题且无法正常选择。4.24增加24字节wrapper，只对635返回自身，其余重放按新PC修正的ADRP并返回原入口+4。RX尾部扩24字节，不增加文件大小，不改动态重定位。

A7M4方案提示的descriptor+0x2A可见标志，R5已有1，无需照搬。两种TextRow标题生产者经原getter取得02FF4230，再由既有hook转“自定义滤镜”。缓存依据原代码访问范围核对，不能声称恢复了精确C数组边界。三种加载偏移、1589旧键、普通/缓存两facade、标题两生产者与4.23失败/4.24成功均有回放；78组进入、108回调、6组push/pop、12组presenter等通过。图形服务/树/分配器有fixture，不等于真实字体LCD或Sony全事件循环。

## BIN v4与整套参数生命周期

仅接受magic `R5CUST4` 加零尾字节，128字节头、2452字节记录，最多12条/29552字节。number1–12为独立配置ID；简写24字节、全称64字节存储区，严格UTF-8及终止/保留检查。每项含完整CC1、block13、129点Gamma和1215字节强制网格。零系数是自定义零修正，不等于自动选择原厂网格或关闭全部原厂处理。

| 事件 | 文件/运行时行为 |
|---|---|
| 启动/普通恢复会话 | 会话epoch隔离旧事务；先载内部保存集，再有限窗口扫描SD |
| SD有效BIN | 完整替换，未列项删除；零字节文件或有效空集清空配置 |
| SD文件缺失/损坏 | 保持内部已有配置，不等于恢复原厂 |
| 更新/更换 | NEW独占暂存、fsync、读回、rename及目录fsync；SEAL准备，SELECT发布不可变活动视图 |
| 选择保存 | 独立24字节R5FILTER.BIN保存配置ID，0为关闭；先保存再SELECT；匹配CRC/serial/epoch ACK后刷新 |
| 当前所选配置被删 | 选择落到关闭，走原厂参数与网格恢复；旧请求仍持有其捕获代际 |
| 关闭 | 原厂基底仍由创意外观决定；撤销自定义覆盖，不修改原厂Creative Look ID |

CC1/block13/Gamma/网格共同受已发布代际控制，避免未封存/过期事务暴露半组数据。Gamma原记录576字节，只替换前516字节129点；尾60字节从实际基底及part保留，包含原生附加处理引用。覆盖已知参数不会删除YGain/Knee、局部色度或补偿链。统一生命周期有离线验证，但尚无逐帧CC1、Gamma和网格原子更新证明。

4.23/4.24 CP每代分配522152字节，16代约7.967MiB，另加原厂allocator开销；AP最多16个不可变名称代际，菜单切换不增加配置代际。资源失败明确回退/关闭并诊断，不能宣称设备资源一定足够。4.24 CP等于冻结4.23，继承测试不冒充本轮重跑。

## 保留4.22网格生命周期：请求、交付与原厂恢复

统一在 `0x719F16` controller调用边界捕获generation/slot/level；五处旧selector/guard/validator/retry detour撤销回原厂。覆盖direct index0–2、原厂条件允许的index3/direct1，以及已复现的root1=1/domain6/non-direct/index3。自定义405-word/1620字节表预建且不可变；延迟请求、AA两lane、writer和复制消费者用同一捕获代际。

加载、同ID更新和切换交付对应不可变表；有效自定义仍遵守原厂enable及晚packet门。显式关闭自定义网格交付enable0/bank0/submit0；清空或漏配导致回退原厂时，则从本次controller实际选择的raw/kind/transform复制源，再调用原厂builder生成独立packed表，保留原生强度与门控。不能用固定全局work区或猜测源地址代替真实原厂源。

恢复缓存按实际源字节、nullness、kind、transform、level分类判等；同地址内容改变须新建。每代32物理项，最多31个READY/承诺项，留一个snapshot暂存槽。满后已知key仍可复用；新内容容量不足、争用/BUILDING、未知状态或OOM明确关闭当前阶段并记原因，不在拍摄热路径无限分配，不原地覆盖旧表。

4.22最终204组完整交付、411组恢复/连续生命周期及两lane/旧代延迟消费等通过；4.23改变独立选择后又有对应继承/集成验证。原厂RAM源在复制1215/162字节期间的生产者并发原子性、真实缓存一致性、31项长期容量和JPG像素仍待机身。软件上传调用不等于硬件完成或像素验收。

## Web工作台、原厂网格与色卡目标

当前独立Web在 `R5ColorLab/`，只输出v4。拟合CC1/block13/Gamma后，必须显式选择原厂网格或完成与源参数绑定的压缩才可导出；服务端检查来源与绑定，空导出集仍可用于清空。原厂网格以资源号展示，尚未证明每个资源号对应哪个外观，不能随意贴ST/PT等确定标签。选择原厂网格只替换该网格，不重置其他参数。

原厂1215字节系数到packed格式是原生整数打包，不因长度变化缩小矩阵；将任意LUT压缩为有限整数网格则可能有拟合/量化误差。强度是原生网格偏移程度控制，不能当enable；精确像素响应仍需R5实测。

新任务默认旧版暂定BT.601/三线性/固定响应模型，可选QAQ c8328ad5 A7C2 2.01实测代理；现有任务绑定模型不随切换改写。QAQ通过零表、三轴探针、ramp及留出等实拍建立逆坐标B样条和TPS前向响应，并非从固件直接得到R5色彩算法。R5需先证明探针影响SD JPG，再固定外观、曝光、WB采集多探针与留出图建立自己的标定；软件色卡导入不能替代这一步。

支持下载2368×1600、74×50格、3700点ST颜色子链模型色卡，用户软件全局调色后导入8/16位RGB TIFF或8位JPG，中心16×16均值作为目标。严格检查尺寸、方向与ICC；无ICC按sRGB，其他色域需先转换。保留实采输入及训练/验证/测试划分；此图不是原始ARW，也不是重新拍摄标定。色卡目标不提供任意RAW的目标双图渲染。发布测试以 `publication/4.24/checks.json` 为准。

## 当前证据索引

以下目录标识用于定位原始日志与实现；公开仓库只收录许可范围内源码及精选脱敏回执，缺失原机资料不构造下载链接：

- `analysis/r5_custom_menu424_20261023/`：第二ID通路、标题/缓存、主菜单正反回放、最终门控/独立解密。
- `analysis/r5_custom_filter423_20261023/`：独立菜单、BIN v4、选择保存、AP/CP与资源代际。
- `analysis/r5_grid_restore422_20261023/`：统一交付、原厂源重建及生命周期回放。
- `analysis/r5_runtime_load421_20261022/`：会话/文件/跨核事务生命周期。
- `analysis/r5_grid_preview_jpg_reason_20261023/`：实机现象、enable纠错和缓冲区组合缺口。
- `analysis/r5_st_pt_fl2_private_pipeline_20261023/`：YGain/Knee和PT私有链路，亮差未最终定位。
- `analysis/qaq_latest_20261022/`：QAQ代理身份和适用范围。

---

## 历史记录（以下截至各节日期，4.18方案不再是当前格式）

# 4.18历史方案与早期研究档案

更新：2026-10-21。本节是当时方案的历史记录；原始采集、执行源码、测试回执继续原路径保存。当时固件为 **4.18（版本字节 `18 04`）**，用户已确认实机结果没问题。下文的具体离线测试、历史实拍测量与用户综合实机反馈分别列示，不互相替代。

## 当前交付与保留范围

保留原版、严格4.03、4.04、4.18的固件包。严格4.03是4.04的固定构建输入，区别于历史失败4.03。此处为当时保留清单；4.18/4.19包随后已清理，4.20–4.24交付另见当前记录。其他早期版本生成包及可重建大型中间件已清理；源码、执行日志、散列与事故证据保留。4.18仍依赖少量4.07 AP前缀、4.13 AP分区及4.16 BCD封装源码，这些只是构建输入，不是保留可刷版本。

首次完整备份 `backups/R5_4.00_20261014_full/`、首次采集 `analysis/r5_live_system_20261014/` 不允许修改、移动或删除。所有原始DAT、签名密钥和机身镜像继续本地保留，不随GitHub发布。

| 4.18交付 | SHA-256 |
|---|---|
| BODYDATA.DAT，754,525,608字节 | `bbf7f372f2f752c0f2fc0380cc2b027fae286e05f691283c61c12e15f0a23363` |
| AP appFw.so | `24a39a7969cce373eef761b1e220a8c852a5688501e641dc48c81ff6b88b16a8` |
| CP cpapp-b.bin | `0365791a235701e033fe2003b3e5f1f3c11e55e3f9ce12f3bc97035fad52ff8b` |

源码入口：`analysis/r5_native_overwrite418_20261021/`。DAT本地路径：`research/r5_custom_lut/build_r5_4.18_native12_20261021/BODYDATA.DAT`。当时GitHub仅公开方案和主机源码；本次按用户授权将4.24完整DAT另置Release，原机镜像、密钥及私人照片不公开。

## 一、4.18 自定义滤镜方案

### 1. 按原生外观覆盖

4.18直接按原生创意外观1–12序号导入名称及参数，复用原生外观选择与成像路径。已经替代4.14–4.17的六槽标记、owner扩栈和Q身份方案。基线为4.04原生CP与已验证启动的4.07 AP前缀，复用有限SD扫描、独立文件保存和AP→CP上传。

| 序号 | 原生外观 | 序号 | 原生外观 |
|---:|---|---:|---|
| 1 | ST | 7 | FL2 |
| 2 | PT | 8 | FL3 |
| 3 | NT | 9 | IN |
| 4 | VV | 10 | SH |
| 5 | VV2 | 11 | BW |
| 6 | FL | 12 | SE |

序号不是AP设置枚举或CP wire直接加1。CP wire映射依次为 `[0,3,2,1,16,15,19,20,17,18,5,13]`。

### 2. 参数文件、名称与保存

文件名 **`R5NATIVE.BIN`**，magic `R5NAT12\0`，格式版本2：128字节头，加1–12条排序的1200字节记录。每条包含：

- `number`：1–12；`name`：1–31个UTF-8字节，无控制字符。
- `cc1_delta`：3×8个int16，依次为B、A1−B、A2−B。
- `block13`：3×16×6个int16，包含B、A1、A2全部端点。
- `gamma_native_129`：129个uint32，零起点、单调且在原生范围内。

严格检查机型、基线身份、大小、CRC、保留字段、重复序号及值域。格式中没有原生指针、校准、Gamma尾部、任意地址或额外补偿字段。旧 `R5LOOK.BIN` 不是4.18输入。

启动时先读取内部 `/usr/data/lut/R5NATIVE.BIN`，随后在有限扫描窗口内读取SD卡根目录的新文件，按序号合并。未提供的外观保留以前保存的覆盖；从未覆盖的沿用原厂。内部文件使用NEW暂存、fsync、重读校验、rename与目录fsync，失败保留已有文件。没有卡或卡上没有新文件时仍加载内部保存集；删掉卡上的BIN不会恢复原厂。当前没有热插卡导入或机内复原按钮；恢复某外观需再次导入该外观经核验的原厂完整参数。

这是独立文件持久化与运行时覆盖，**不改写原厂BK4或个人设置字段**。上电时消费者从封存参数组取值，切换外观继续按原生序号选择。名字与参数共同保存；仅在匹配的最终SEAL ACK后替换菜单文字。光栅图标、RAW/JPEG外观标记以及所有右栏缩写没有统一重命名；中文字体和截断需按实际显示判断。

### 3. 成像接入与Gamma

CP以原生state+2e的wire及context+25的profile定位导入参数。CC1在 `0x71e726` 替换48字节源指针，保留原厂调整和运算。block13接入原三端点与16色相消费者；保留机身校准及特殊条件。BW/SE原本会绕过普通矩阵，已增加有导入才生效的资格分支；后续黑白/棕褐语义仍保留，覆盖它们不等于转换成任意彩色模式。

Gamma不能直接改共享原记录，否则ST/NT等别名会互相影响。4.18为12项建立独立ID51–74及所需三种原576字节记录，只覆盖前516字节129点，尾60字节原生元数据保留。ST另有normal enum0路由，使用影子表接入；其他57行normal路由和旧ID0–50保持。11处getter及CC1、block13统一以整组ready门控；未准备好、分配失败或未确认时回退原厂。

首次探测分配37,612字节堆（14,128字节bank加23,484字节Gamma）；状态BSS32字节仍在原末页，不引入旧4.05的大Q表。原请求保留旧ID，后续重新选择才用新ID；验证导入后可切到其他外观再切回。**额外补偿矩阵和残差网格均未加入固件。**

### 4. 完整操作流程

首次从原厂安装仍需完成下方历史4.04章节的进入、完整备份与本机签名信任环境建立。签名信任修改不是SD参数导入，不能用别的机身或历史设置整区替代当前机身数据。当前4.18的参数覆盖不需要每次另行fastboot写颜色。

1. 核对机型、签名环境、备份与已确认可启动基线；先准备完整工具和文件，再进入设备模式。新机身不得直接复用本机载荷及设置。
2. 本地重建时先生成并核验AP模块及分区、CP消费者、Gamma门控和名称钩子，再运行 `package_native418.py`。复用原R5升级器、WBI与模板；TAR仅替换nflasha15、nflasha8及part_image.sum。采用只读TAR overlay节省空间，原件不改。
3. 运行 `verify_delivery.py` 核对来源快照、交付散列、组件反向差分及回放绑定。封装完整独立解密、RSA验签、篡改拒绝和CRC均需通过。版本按BCD `18 04` 核对，禁止沿用十进制18→0x12的错误编码。
4. 将已核验的4.18包命名 `BODYDATA.DAT`，按机身SD更新流程升级。电量、卡槽与操作遵循原厂要求；更新中不运行fastboot，不把1/3/5闪当作写入进度。
5. 使用配置工具生成 `R5NATIVE.BIN`，放SD卡根目录，正常关机后重新开机，等待启动导入。菜单选中目标项，并切换外观一次检查实际效果。
6. 分别验收名称、预览、JPEG、关机后保持、移除卡文件后保持，以及再次只导入一个序号时其他覆盖是否保留。fastboot回读独立内部文件可证明存储状态，不能替代运行时CP确认和照片验收。
7. 恢复覆盖时使用经核验的原厂参数文件；当前无通用reset命令。无法启动时停止正常导入流程，按故障证据和对应恢复方案处理，不盲刷历史完整镜像。

公开仓库不含必需的原厂AP/CP、分区、私钥、BootROM、Edit运行时或外部引导包，因此不是下载后即可给任意机身刷入的一键安装器。执行源码中的固定散列失败时停止，不删除校验继续。

### 5. 生成与验证参数文件

从仓库根目录运行，JSON结构以 `import/native_overwrite_config.py` 的严格检查为准：

```sh
python analysis/r5_native_overwrite418_20261021/import/native_overwrite_config.py pack native_config.json --output R5NATIVE.BIN
```

拟合配方需同时提供对应本地运行时capture，严格换算并保存审计文件：

```sh
python analysis/r5_native_overwrite418_20261021/import/native_overwrite_config.py from-fit recipe.json --capture CAPTURE_DIR --number 1 --name SLOG3_709 --output native_config.json
```

工具拒绝覆盖现有输出。其早期回执中的 `installable=False` / `camera_reader_installed=False` 是编译器本身不检查相机安装状态的保守字段，不能当作4.18交付未加入读取器；实际交付状态以本节及完整DAT证据为准。

本地对比文件 `parameters_4.18_pt_fl2_FL_compare_20261021/R5NATIVE.BIN` 为2528字节，SHA-256 `3ef4cdcb8ff4df7363e47d2f1ce6fe06bb591e967d2d0ab5eb0350bb5ed3f458`：2 PT→`pt+`、7 FL2→`fl2+`，两项均为原R5 FL完整CC1、block13、Gamma，用来观察覆盖与名字，不是S-Log3拟合精度样例。

### 6. 证据与当前验收

4.18完整DAT的独立解密、RSA/OpenSSL、篡改拒绝与CRC通过。4095种mask、146项真实A64文件worker场景、49257项名称路径、104项AP/CP探测、108项上传及9类敌对事务通过。消费者回放含48项自定义/312项原厂CC1、912项自定义/2904项原厂矩阵、168项完整原生调用链；Gamma含600项完整路由、48项setup/consumer、651项差分和2464项getter检查。底层介质、RTOS及部分libc/绘制仍由模拟边界承接。

2026-10-21用户明确反馈：**“4.18实机结果没问题”**。这是当前实机综合验收反馈；没有另行取得每种模式、长期保持及颜色误差的逐项新测量，不能从此推断拟合器的LUT颜色精度通过。

### 7. 本地 Web 色彩工作台（2026-10-21）

用户确认“所有原厂参数”范围为现有全部颜色参数：12种创意外观、完整CC1三端点、block13三端点和129点Gamma。菜单对比度、高光、阴影、锐度等不在当前4.18文件字段中，本轮未扩展固件协议。

双击根目录 `启动R5色彩工作台.command`，自动检查依赖、启动仅监听 `127.0.0.1:4180` 的服务并打开浏览器；端口占用时可传 `--port 4181`。运行时可通过 `R5_COLOR_PYTHON` 指向兼容Python 3.12。页面支持12项选择、参数表格与Gamma图形编辑、3D `.cube` LUT导入（S-Gamut3 / S-Gamut3.Cine）、现有拟合器、测试集误差与多外观配置导出。导出ZIP包含 `R5NATIVE.BIN`、`native_config.json` 和SHA回执；拟合任务保留配方、审计、日志，服务重启后可从历史任务恢复。

后端复用 `validate_synthetic_pairs.py`、`RawSLog3Reference`、`fit_full_chain_native.py` 和4.18 `native_overwrite_config.py`；保持固定ST/context4合成RAW前端、训练／验证／独立测试划分、fused参考模式与无补偿策略。导出前严格检查所有值域、单调Gamma、CRC、基线身份、重复序号和名称编码；默认保留已验证ST Gamma末端，超出时拒绝转换，另有显式131071开发值选项。没有相机操作、设备命令、任意本地文件读取或联网。

本轮验证：Web适配6项回归、HTTP接口6项检查通过；浏览器实际导入 `SL3SG3toTealOR_709.cube`，完成低迭代端到端拟合、严格转换、测试色块与误差显示，并组合ST／FL下载2528字节BIN，独立确认magic、序号与SHA一致。测试MAE17.506、RMSE23.202、P9552.051仅证明流程接通，不能替代完整颜色精度或实机验收；默认末端拒绝任务和日志均保留。未修改固件、历史源码、首次备份或原始资料。

2026-10-21 后续 Web 更新：测试色卡已加入4个传感器正色、256级完整等通道灰阶、24项 ColorChecker Classic（BabelColor Average、ICC D50）。标准xyY经ProPhoto及当前相机配置反变换到RAW，不直接使用sRGB数值；这是数学标准色卡，不代表物理色卡拍摄。新合成RAW全部64,749,568个像素经独立LibRaw解码无差异；284个必拟合色块前端由临时独立Edit副本实际采集，无插值。颜色模型仍使用原已验证ST/context4，新增采集只贡献pre-matrix输入，不把采集时当前外观输出混作ST结果。随机测试740项保持独立，色卡误差明确列为训练误差。

`web/fit_anchor_native.py`为新适配器，历史脚本不改。Gamma从32个控制点扩展为全部128个RAW节点，零点固定，127个正增量与上界余量共同优化；配置第129点在RAW上下文中不存在，仍使用单独端点策略，不声称完成129点机内拟合。随机、正色、灰阶、24色四组总平方损失均衡。新增“原始输出／扣除各自纯黑输出”对比，公式为逐通道`max(RGB - 零传感器RGB的输出, 0)`，不拉伸，且不改变优化目标或导出。原始和扣黑误差同时保留，不能把扣黑指标当原始还原精度。

当前验证任务`4ebc6bf4a2af4499827741ef310b98be`：24色训练RMSE5.96、正色2.12、灰阶5.32；独立随机测试MAE5.58、RMSE7.83、P9514.97（历史8位量级定义：14bit误差除64）。扣黑RMSE9.75；扣黑并没有消除剩余色调误差。12项回归、JS语法检查、页面切换、严格配置转换及新RAW传感器／其它外观不变检查通过；尚未通过完整Edit JPEG或实拍颜色验收。证据目录`research/r5_custom_lut/evidence/web_chart24_20261021/`，保留chart、原生frontend_capture、dataset_audit、verification_fit及raw_validation。旧260色卡原始采集和旧任务保持可追溯。所有操作本地，不访问相机。

用户随后明确取消扣黑。当前页面和诊断API已移除扣黑口径，双方统一按`floor(clip(RGB,0,1)*255+0.5)`生成uint8，误差直接对8位整数相减。独立测试按目标编码亮度`Y′=.2126R+.7152G+.0722B`划分：阴影<85、中间调[85,170)、高光≥170；同对样本共同归组。页面总误差与色卡误差使用此新口径；历史recipe/log中的14bit除64仍保留为旧记录，不再作为页面当前统计。上述任务：全部740项MAE5.57/RMSE7.82/P9515；阴影595项RMSE6.30、中间调137项12.44、高光8项7.49。高光样本少，不代表精度充分验证。12项回归覆盖量化、分区边界及空组，页面阴影切换验证通过；优化和导出参数未因统计口径改变。



## 二、RAW→S-Log3→LUT 与 Edit 原生链路拟合

### 1. 目标与数学模型

目标是对同一传感器输入s拟合两条完整链路：

`目标 T(s) = LUT(SLog3(色域转换(白平衡与RAW前端(s)))))`

`原生 Fθ(s) = Edit完整RAW→JPEG链路(s；CC1、block13、Gamma = θ)`

优化 `Σ训练点 w·|Fθ(s)−T(s)|²`，保留独立验证与测试集。不能把已过ST的图直接套S-Log3 LUT当完整输入，也不能只用实拍照片像素拟合后声称得到通用传感器转换。按用户要求，以Edit与机内原生创意外观处理一致作为工程假设；该假设不算实机独立测量。

目标前端采用Raw Alchemy 0.6.2经核对的分支：传感器去黑/归一化→白平衡→相机到ProPhoto→上界裁剪→EV与合并调色的负值截零→S-Gamut3或Cine矩阵→最小1e−6→16384节点S-Log3表→四面体cube→输出裁剪。S-Log3锚点：黑95/1023、18%灰420/1023。LUT的709名称不足以证明输出TRC，不额外凭名称套sRGB曲线。

当前应显式使用 `raw-alchemy-v0.6.2-fused` 模式。旧未截零数学模式仅供历史重放。去马赛克邻域、高光重建等空间处理不由平场逐颜色模型完整覆盖；目标不是已证明与Sony机内视频S-Log3逐像素相等。

### 2. 原生参数与RAW的转换

完整十字段、共用字段及原厂来源见后文研究章节。拟合器实际优化可变化的CC1、16色相block13及Gamma；各滤镜共用且已核对的字段沿原厂路径，不为凑“十字段全改”而修改。

| 拟合RAW表示 | 4.18原生表示及限制 |
|---|---|
| CC1直接八项 | 前四项顺序 `(1,2,3,0)`；后四项按 `(5,6,7,4)` 半值舍入。反换算存在量化误差，审计中记录 |
| 780F 16×6系数 | 读取保留符号位的int16并右移2，色相索引 `s^1`；不以浮点重算破坏原位域 |
| 7806 128点曲线 | 原生前128点由RAW值除2舍入；第129点RAW缺失，须保留经核验原生终点或显式指定 |
| 三端点 | 当前拟合导出策略为CC1差分0、block13的B=A1=A2；不是三个照明端点独立拟合。原生FL/FL2/FL3完整迁移仍保留各自三端点 |
| 额外补偿 | 4.18未包含矩阵/网格；PC残差实验不混入固件输入 |

Gamma文件支持129点完整导入，不因RAW只有128点而缩减格式；原生记录尾部元数据仍由机身提供，不能由RAW猜出或序列化任意指针。

### 3. PC研究和交付步骤

1. 从RAW元数据建立相机/WB/色域参考，固定EV、白平衡、输入和LUT散列；统一使用fused目标模式。
2. 生成合成RAW色块，采集Edit前端输入与原生输出，固定空间训练/验证/测试划分；实拍仅用于留出校验。
3. `fit_full_chain_native.py` 连续松弛初始化，随后量化并评估实际整数CC1、block13及Gamma。验证集选择参数，测试集不参与选择。
4. `write_fitted_st_raw.py` 在RAW副本的ST参数中写入拟合值，保留传感器数据和其他外观；在Edit显式选择替换后的ST，关闭镜头补偿后导出。原片不改。
5. 用相同坐标、曝光、白平衡和输出编码比较目标TIFF与Edit输出，报告MAE、分位数、最大值、暗部/肤色/饱和边界；不只报平均误差。
6. 验收合格后才将配方用 `from-fit` 转为4.18 JSON/BIN。文件换算成功、机内导入成功、颜色拟合合格是三件事。

源码主要在 `research/r5_custom_lut/scripts/`：`raw_slog3_reference.py`、`build_raw_slog3_reference.py`、`build_full_chain_pairs.py`、`edit_raw_front.py`、`edit_color_pipeline.py`、`edit_parameter_context.py`、`fit_full_chain_native.py`、`edit_native_recipe.py`、`write_fitted_st_raw.py`。公开版本把个人路径改为显式输入；Edit程序、运行时转储、用户RAW/TIFF和商业LUT须由研究者自行提供，不分发。

### 4. 有效结果和未完成项

第一批TIFF因用户未关镜头补偿已作废。当前依据第二批四张无镜头矫正、9566×6374、RGB16位TIFF；固定3700点与原测试划分。找到Raw Alchemy合并图中Log矩阵前的负值截零后，目标数学链与实际导出核对如下，单位为8位等效码值MAE：

| 对照 | S-Gamut3 | S-Gamut3.Cine |
|---|---:|---:|
| 数学RAW→Log 对实际TIFF | 0.00357 | 0.00362 |
| 数学RAW→LUT 对实际TIFF | 0.00619 | 0.00588 |
| Log TIFF套同一cube 对实际还原TIFF | 0.00150 | 0.00155 |

全部点纳入主指标。7处高亮色块仍有明显异常，Log最大差8.69/8.03；尚未完整重放邻域高光重建，不能称全域精确。

第二批Edit输出已明确选择替换ST；原生最终像素与JPEG归属核对MAE为0.6330/0.6360，这只是导出归属校验。**最终拟合图仍暗灰，LUT还原颜色精度未通过。** 当前不能宣称原生拟合优于作者ST后套LUT，或已达到任意LUT精确复现。剩余方向是完善完整输出及空间前端模型、约束优化和更多独立场景验证；引入残差网格需要另行固件需求和阶段位置证据。

## 三、失败教训与升级原则

- 不从失败4.03、旧两槽初始化/保护或历史模板继续叠补；严格4.03与失败同版本包分开。
- 不再把额外设置迁移、Backup专项同步、finalizer、成功标记或重复WBI清头塞进SD收尾。4.05黑屏的具体根因没有锁定，不把某一猜测写成定论。
- 原厂模板、镜像、运行RAM和CP消费者分别验证。封装正确不证明能启动，菜单可选不证明颜色正确，写后回读不证明重启保持。
- 设备会话须先准备后连续执行，不在fastboot内长时间等待；接口消失或校验不符停止。临时引导不等于零风险，也不凭红屏推定fastboot持久损坏。
- 新版只维护本文件的当前结论；旧源码与原始日志保留作为证据，旧文中的“当前”按历史时间理解。

## 四、参考项目与致谢

特别感谢 [Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware)，FL2/FL3方案固定提交 `086df3b1e33dfa0206553ac2bb003535c58ddb80`；感谢 [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) 的BootROM、串行引导、fastboot与存储研究。

自定义外观参考 [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research)，参考提交 `008a12f2b8d79f04ffa405d5d4ce2546b2a3db42`（feature/lut-device-import）；目标RAW链参考Raw Alchemy 0.6.2与Colour，容器工具参考DavidBuchanan314/ma1co fwtool。各项目的贡献、固定版本与许可边界见仓库 `THIRD_PARTY_NOTICES.md`，致谢不构成二进制再分发授权。

以下为仍有效的4.04完整刷写、FL2/FL3十字段换算、共用参数追查与实拍证据。**其中4.04的个人设置部署不是4.18自定义文件的保存方法**；保留它以便复现FL2/FL3基础及原生参数来源。

---
## 一、完整刷写方案

### 0．适用范围、当前状态与执行顺序

本方案针对本工作区已核验的R5 4.00 CN2基线、匹配的本机签名身份与4.04交付物，不能直接套用到另一机身／地区／版本。文中命令供后续实际部署时使用；本次文档整理没有运行设备命令。

从原厂状态首次安装时，作者顺序是：**进入fastboot并备份→建立自签信任环境→部署本机个人设置／颜色→正常启动并SD升级→升级后重新读取和验收，必要时重建设置。** 用户要求的四部分按“备份、校验镜像、SD升级、升级后系统覆盖参数”组织；作者的SD前设置部署使用第4步同一套流程，SD后仍须核查。

本机的实际记录是：一号分区信任环境已部署；D在4.03状态写入设置并回读；之后手动升级4.04；I发现六槽及颜色记录等于原厂，但两处CP已是目标4.04；T再次基于新回读部署设置成功。只有D／I两快照不能确定设置恢复发生于首次重启、SD更新或后续初始化，因此不把“SD必定清零”写成规则。

| 机身目前状态 | 需要做什么 |
|---|---|
| 首次安装、未建立本机自签信任环境 | 完成本节全部环节，先核实一号分区基线，再制作对应候选 |
| 已建立匹配信任环境、尚未安装4.04 | 核对当前状态与备份，按作者顺序部署设置，再SD更新，更新后重新验收 |
| 已是4.04且设置缺失 | 基于当前新回读执行第4步；不要为补设置而重刷DAT或一号分区 |
| 已写入目标设置、仅缺重启后验收 | 先执行只读回查和实拍；确认缺失后才重新部署 |
| 正在SD更新、升级中断或不能正常启动 | 不套用正常安装命令；先保留现场与日志，单独判断恢复路径 |

### 准备：设备、文件与主机依赖

1. 使用供电稳定、达到原厂更新电量要求的本机电池；确认没有正在进行SD更新，记录当前版本及电源状态。同一电脑只连接这台待处理机身。
2. 改装线连接相机Multi口，负责复位和串行引导；另用USB-C数据线连接相机与电脑，负责fastboot数据传输。已有成功记录不能证明ON或OFF是进入的必要条件，操作前须记录实际状态。
3. 使用现有RP2040 `uart_boot 1`固件：GPIO28→相机RX、GPIO29→相机TX、GPIO27→复位，`OPEN_DRAIN`构建，链路48000波特。构建和UF2身份见[魔改线构建记录](../build_uart_boot_20261013/README.md)。已正常工作的改装线不需重新刷写UF2。
4. 主机使用本工作区`.venv/bin/python`；USB工具在`analysis/r5_live_system_20261014/host_tools/`；部署过程中用macOS的`/usr/bin/clang`、IOKit、CoreFoundation编译限定写入程序。先准备好依赖再进入，不能在fastboot内等待安装工具。
5. 原工具包位于`/Users/LOCAL_USER/Downloads/bootloader脚本.zip`。已执行源码副本保存在D会话的`execution_source_snapshot/`，但当前脚本仍读取原工具包路径；不可仅移动工具包而不检查依赖。
6. 首次备份、源DAT、R5／FX2原始解包、严格4.03构建源、本机公私钥、4.04构建及执行脚本保持原样。历史失败4.03和旧两槽脚本不作为入口。

以下命令从工作区根目录执行。先用只读文件枚举确认本次串口，再填写`R5_PORT`；示例`/dev/cu.usbmodem101`不是永久端口。所有会话目录必须是新的、尚不存在的路径：

```sh
cd /path/to/r5-workspace
python3 -c 'from pathlib import Path; print("\n".join(str(p) for p in Path("/dev").glob("cu.usbmodem*")))'
R5_PORT=/dev/cu.usbmodem101
R5_SESSION_TAG=$(date +%Y%m%d_%H%M%S)
```

执行前核对四个核心脚本，预期值如下；不要修改脚本来放宽校验或调整进入时序：

```sh
shasum -a 256 tools/run_r5_m4strict_personal.py tools/deploy_r5_m4strict_personal.py tools/r5_settings_ram_boot.py tools/build_r5_m4strict_personal.py
```

| 脚本 | D／T使用的SHA-256 |
|---|---|
| `run_r5_m4strict_personal.py` | `658afda1a6eb9235f9d48096b604e943a2b71fbf99dc9c19a68af355df978675` |
| `deploy_r5_m4strict_personal.py` | `e189cda6405ca03fd9f0617ebf4677d63c90d17553a3623efc6adacbdc716120` |
| `r5_settings_ram_boot.py` | `80b79977a51bdfdfb5d8947ff92192ec04d803df3dbc2d0f79d2a634500329d8` |
| `build_r5_m4strict_personal.py` | `a95187c2d6dcb5633f74c35f10ab5a687216b624f542a7af56a5dd79763132ce` |

### 1．进入fastboot与备份

#### 1.1 入口动作和成功判据

原入口依次执行RP2040握手→相机复位→开启载波→等待原工具的`TRANSMIT_START`（0.5秒）→按`boot_script`发送引导记录及间隔→关闭载波→切换115200波特接收输出→配置相机USB接口并查询fastboot。

发送的是临时SRAM载荷及引导参数，不是向机内存储分区刷写`fastboot.bin`。这一步仍会复位并运行临时代码，不能承诺零风险，也不能把历史红屏直接诊断为持久fastboot分区损坏。保持已核验载荷SHA-256：`330ac322bd0e40a7bb4974f69a2667e7d59a25e59c1322339690f30a3ceadbdc`。

需要单独进入并进行最小只读身份探测时，可使用：

```sh
R5_ENTRY_RUN="analysis/r5_entry_${R5_SESSION_TAG}"
.venv/bin/python -B tools/r5_settings_ram_boot.py --port "$R5_PORT" --output "$R5_ENTRY_RUN"
```

该入口会查询版本、分区表和设置区首扇区，保存UART、USB查询及`report.json`；**不会主动正常reboot，也不执行持久flash**。成功要求`usb_transport_verified=true`及协议`OKAY0.5`，不能只看短暂黑屏或串口是否出现ready文字。USB描述符和product来自载荷常量，必须继续用本机分区表／ROM核验身份，不能据此认定机型。

首次完整备份和第4步连续部署都自带入口，不应在它们之前机械执行这条单独进入命令。仅单独探测结束且没有待评估写入时，正常退出命令为：

```sh
analysis/r5_live_system_20261014/host_tools/read_fastboot_usb reboot
```

#### 1.2 首次完整采集的范围

本机首次资料固定保留在[原机备份目录](../backups/R5_4.00_20261014_full/)和[首次采集目录](r5_live_system_20261014/)，禁止覆盖、删除、移动或改写。已采集内容包括：

| 对象 | 保存与核验要求 |
|---|---|
| 17个有效SDM2用户分区 | 各完整logical镜像，记录分区起点、扇区数、长度和SHA-256 |
| 已分配用户区raw与SDM2表 | raw覆盖表内最大已分配范围；按绝对扇区AES-XTS独立解密，与所有logical逐字节比较 |
| eMMC boot0／boot1 | 原始镜像各重复采集两份并比较；不作为日常设置恢复目标 |
| 独立CP NOR | 保存原始物理NOR、分段及拼接证据，不能用eMMC CP镜像替代 |
| AP／CP BootROM | 保存ROM参考、采集日志及散列；ROM不是刷写目标 |
| 清单与恢复边界 | 保留`manifest.json`、`verification.json`、`SHA256SUMS`及`restore_inventory.json` |

这是现有清单范围的完整采集；未独立读取EXT_CSD证明整颗eMMC物理容量，不能称已经克隆芯片全部物理空间。

完整采集入口为[backup_r5_all.py](../tools/backup_r5_all.py)，离线核验为[verify_r5_full_backup.py](../tools/verify_r5_full_backup.py)。**它们是历史采集工具：采集间接调用的`r5_boot_probe.py`写死串口`/dev/cu.usbmodem101`，不是通用的`--port`入口；端口不匹配时不能照抄执行，也不要修改已留证源码。** 仅在端口、目标和依赖均匹配、已决定新采集时，命令形式为：

```sh
R5_FULL_RUN="backups/R5_new_acquisition_${R5_SESSION_TAG}"
.venv/bin/python -B tools/backup_r5_all.py --output "$R5_FULL_RUN"
.venv/bin/python -B tools/verify_r5_full_backup.py "$R5_FULL_RUN"
```

第二条会在指定目录写核验结果与恢复清单，因此只能用于本次新目录，**不得对首次备份目录重跑**。前一条只有完成采集后才能进入完整核验；`partial`需按原日志和`resume_r5_raw_backup.py`的限定条件评估补采，不能当成功。原采集包含正常reboot，长传输可能因接口消失分会话补读；没有完整日志、大小和散列就不能进入持久写入阶段。

当前机身已有首次完整备份，后续个人设置修复不必每次重读全部分区，但必须由第4步重新采集当次设置logical/raw、SDM2与AP ROM。历史备份用于身份和恢复参考，不能替代当前设置输入。

### 2．刷写校验相关镜像，建立匹配签名环境

#### 2.1 具体修改与作用

此步处理更新器信任，与FL2／FL3颜色设置、DAT的AES解密不同。使用本机原有RSA密钥对，机内`nflasha1`的`/boot/initrd.img`中替换`/etc/VerificationKey.pem`；四个更新库的`verifyKey()`入口各覆盖8字节，使其返回0：

- `/usr/lib/libupdaterapi.so`
- `/usr/lib/libsdfileinputupdaterapi.so`
- `/usr/lib/libseninputupdaterapi.so`
- `/usr/lib/libuudfileinputupdaterapi.so`

后续`VerifySignature`／RSA验签代码保持原样，DAT仍需由匹配私钥签名，不能安装任意未签名文件。同步重算`p1chksum`，保留FAT和SquashFS元数据。这里绕过的是原公钥信任检查；**4.04没有新增同版本／降级条件绕过**，其检查仍按交付包原有逻辑执行。

#### 2.2 候选、写入与回读

已有候选位于[一号分区构建目录](../build_r5_partition1_verifykey_skip_20261014/)，logical镜像为`nflasha1.R5_4.00.custom-key.verifykey-skip.logical.img`，25,100,288字节，SHA-256：`0ec7813c78f121f5abced7fc24350e34ac4cffa4ec8be4d1ecccee22f3d4922d`。公钥身份SHA-256为`4cb3cf8cc7a847a5b6108863c2defa327ceb06280c1dda468cd57c3dd3cae859`；不在本文复制私钥。

实际已执行的流程是：

1. 核验首次备份、候选、公钥、私钥配对及四处RSA函数未改；两个独立文件系统解析器核对目标仅涉及PEM／四个库及对应校验。
2. 基于当时机内已验证的“仅换公钥”一号分区制作正向／反向稀疏差异，限定USB写入程序接受的目标与下载散列。
3. 在同一新会话进入fastboot，读取当前SDM2、AP ROM、完整一号分区logical/raw。目标几何应为起始`0x80`、长度`0xbf80`个512字节扇区；独立解密与当前预期基线完全相同才继续。
4. 只发送候选稀疏数据及`flash:nflasha1`，当次设备应答写入233扇区。
5. 重新读取25,100,288字节完整logical/raw及SDM2：logical精确等于候选，49,024个raw扇区独立AES-XTS核验通过，logical/raw变化扇区一致，分区表不变。
6. 全部通过才正常reboot；记录应答和用户恢复拍摄确认。

历史入口为[flash_r5_verifykey_skip.py](../tools/flash_r5_verifykey_skip.py)，其`--prepare-only`与`--flash --port …`分别对应准备和写入。但它固定旧基线、旧候选、旧会话目录，并拒绝已有记录；**不能作为当前新会话的可直接重跑命令**。旧稀疏文件与`restore`同样绑定当时前置状态，不能覆盖当前机身。新机身／不同基线需要另行制作适配的新会话入口，不通过删除历史目录或改固定散列来重用它。

本机该步骤已实际完成，原始[部署报告](r5_verifykey_skip_flash_20261014/report.json)、[flash日志](r5_verifykey_skip_flash_20261014/flash.log)及[独立回读核验](r5_verifykey_skip_flash_20261014/independent-readback-verification.json)均保留。已具备匹配信任环境时跳过重复写入；若怀疑当前环境变化，先新读判断，不能据历史记录断言当前仍相同。

为保留完整历史顺序：本机先通过`build_r5_partition1.py`／`flash_r5_partition1.py`部署仅换公钥的中间镜像，再完成上述verifyKey修正。该中间态SHA-256为`7d17697fb83a26bbcd53f49f7c791fea7cdd9e372ad6f4510d1f079e643a0b05`；它不是最终信任环境，不能只刷中间态就认为全部完成。已有两个历史写入入口均绑定当时状态；新部署应先新读并生成从当前状态到最终候选的已核验差异，不要求机械重走两次历史写入。

### 3．准备已核验DAT，通过SD卡升级

#### 3.1 交付文件和离线检查

使用[当前4.04 DAT](../build_r5_m4strict_4.04_20261015/BODYDATA.DAT)，754,525,608字节；不要使用工作区根目录同名原始包或失败旧4.03。核对文件身份：

```sh
shasum -a 256 build_r5_m4strict_4.04_20261015/BODYDATA.DAT
```

预期`370cd17d50b086e466b987918a95297213eee5dc9f962c77a88f65afdc117dd1`。本次构建的[verification.json](../build_r5_m4strict_4.04_20261015/verification.json)记录736,841块完整独立解密、751,577,088字节明文逐字节匹配，RSA／OpenSSL验签、篡改拒绝、外层CRC及组件一致性全部通过。这里只证明封装与输入一致，不能替代实机安装结果。

已有交付包无需重新构建。开发时如需复现，两种离线入口任选其一，输出目录必须新建：

```sh
.venv/bin/python -B tools/build_r5_m4strict404.py --build "build_r5_404_repack_${R5_SESSION_TAG}"
```

```sh
.venv/bin/python -B tools/build_r5_m4strict_release.py --version 4.04 --build "build_r5_404_from_stock_${R5_SESSION_TAG}"
```

第一条依赖保留的严格4.03构建源；第二条从原厂组件及固定供体重建，需要全部本地依赖和可运行的CP指令模拟环境。两者都不访问相机，不以失败旧4.03为输入。新构建核对它自己的报告与组件身份；不能直接拿旧DAT散列代替新产物核验。

#### 3.2 SD包改了哪些内容

| 组件／位置 | 部署内容 |
|---|---|
| `nflasha15`中的AP | FL2／FL3已有菜单资源、flags、look支持及look10／11→CP color19／20路由 |
| `nflasha8`中的CP | profile54～57选择、CC1／矩阵读取与合法范围、四行内嵌CC1、六条完整Gamma及ID47～50路由、名称和元数据支持 |
| `nflasha5`暖启动镜像 | 经审查的`WBI2→WBI3`标识变化，用于避免恢复旧暖启动快照 |
| 分区校验清单／DAT头部 | 依赖CRC、版本4.04及匹配签名 |
| 原厂更新主体 | 保持原字节；包含原有条件性CP NOR更新链 |

TAR只改AP／CP／WBI三个镜像成员及分区校验成员；原厂默认模板和`backup.sum`不变，个人设置不嵌入通用DAT。不加入旧两槽强制默认／初始化／写保护，不加入项目曾多加的SD设置迁移、Backup专项同步、回读、finalizer、重复WBI清头、成功标记或完成门槛。

#### 3.3 存储卡与机身操作

1. 若是首次按作者顺序安装，先完成第4步的SD前个人设置部署，并确认写后回读和正常启动；不能以DAT签名完成代替颜色数据已部署。
2. 使用相机支持、符合原厂更新要求的存储卡。将**已验散列**的4.04文件以精确文件名`BODYDATA.DAT`放到卡根目录，复制后再次核对卡上文件散列。
3. 线刷会话须已正常结束、相机已恢复拍摄界面。断开改装线及USB数据连接，按本机原厂菜单／指定卡槽的SD更新流程操作，遵守机身电量和版本提示。
4. 更新中保持供电、不要取卡或拔电。1／3／5次闪灯是原厂计时显示，不能视为写入进度或某个分区已完成；不要按灯的次数决定拔电。
5. 以机身更新完成提示、正常重新启动及版本页为基础确认安装，再进入更新后回读。版本页4.04仅是一个验收项，不单独证明AP／CP／NOR及颜色设置全部正确。
6. 若原厂拒绝同版本，停止并保存提示；本4.04没有增加同版本绕过。若长时间异常或出现错误，记录开始时间、屏幕、灯节奏及供电状态后单独排查，不能把本方案当作升级中断后的恢复保证。

原厂`nor_loader_writer.sh`／`nor_update`链受LSI和boot type等条件控制，可能处理loader区域；“保留该链”不等于每次都已经运行成功。只通过fastboot写`nflasha8`不会执行这条原厂链，不能用其替代本步，也不手工照搬M4 NOR写入命令。

### 后续升级预案：SD迁移时保持颜色数据（2026-10-19）

**用户已明确决定：保留我们现有FX2原始B／A1／A2参数，不采用作者最新默认的block13固定A1。** CC1继续转换为B／(A1−B)／(A2−B)，block13继续保留各外观、照片／视频自己的三套原始矩阵。SD颜色保持修复与矩阵端点策略是两项独立选择；参考前者不代表接受后者。本节仅为以后固件升级的适配记录，未加入现有4.04，也未改变历史固定上游`086df3b`。

参考Erlla固定提交[`a15a0cb70b628b94bbd147b6aa53def2b57ed479`](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/a15a0cb70b628b94bbd147b6aa53def2b57ed479)，具体修复提交为`afe335a218be0ad635b6c042cae97e26d14cfa76`。作者的方法是在电脑打包阶段补全SD包内的通用BK4颜色模板，修复模板自身BK4 byte sum及`0111_backup_sum/backup.sum`对应CRC，然后沿原封装／签名／迁移链处理。**不是额外添加机内迁移脚本、服务调用、显式Backup同步或更新收尾动作。** 作者说明见[SD颜色保持](https://github.com/Erlla/sony-a7m4-custom-firmware/blob/a15a0cb70b628b94bbd147b6aa53def2b57ed479/methods/03-fl2-fl3/sd-colour-preservation.md)；相关源码、测试、说明与MIT许可证已本地归档，[文件清单及散列](../references/erlla_sd_colour_preservation_20261019/manifest.json)。归档仅供审查，不作为构建或刷写入口。

作者在M4官方6.02基线处理LS／LS_GLEE各16份，共32份模板。每份十处颜色字段、2504字节：CC1映射4字节、四bank有效系数各48字节、block13映射4字节、四bank三组矩阵各576字节；另重算校验。其SD模板修复保留各bank尾部、LOOK默认槽、reset数据及其他校准；这与历史个人设置部署复制四个完整768字节bank的范围不同，不应将两者的字节数混用。

以后R5升级适配按以下边界实施：

1. 以目标版本原厂R5包为基线，独立枚举全部地区／型号模板及其校验索引，验证实际迁移路线；不能照抄M4的32份数量、目录、分区号或地址。
2. 只补FL2／FL3映射与颜色字段。CC1三组按R5差分格式转换；block13采用FX2原始B／A1／A2，等价于作者的显式`dynamic`数据策略，不采用默认`fixed-a1`。各外观与照片／视频bank独立匹配，不混用；供体及目标模板须有精确散列与格式校验。
3. 不嵌入本机或其他机身个人镜像；不修改LOOK默认槽、复位数据、白平衡／机身校准或无关字段。模板中非目标数据及尾部必须保持该R5基线原值；未知非零前置值、坏校验、重复记录、漏模板应停止，而非覆盖猜测。
4. 重算受影响BK4校验和、模板CRC及容器所需校验／签名；完整重解包核对。增加颜色字段之外的修改需独立需求和证据；不重引入历史额外SD迁移、同步、finalizer、重复WBI清头及成功标记。
5. 离线通过后仍需分别验收：实际SD完成、正常启动、设置与六槽保持、目标CP的eMMC／物理NOR一致、实拍元数据与颜色。更新后应从新的本机回读检查，异常时局部重建，不能回刷历史整区。此方法不保证首次原厂机身仅靠卡刷即可启用，也不保证恢复出厂后保持。

作者新公开修复的直接验证包含真实M4模板的离线对照；不能替代新完整包的实机验收，更不能证明R5已有同样迁移原因。R5目前只确认D至I之间发生过设置／颜色恢复，具体丢失时点仍未定位。本次只记录预案及保留参考材料，未生成新DAT、修改部署代码或访问相机。

### 4．基于新回读，线刷个人设置与颜色覆盖参数

#### 4.1 允许改动的完整清单

设置位于本机`nflasha2`的`BACKUP.BIN`和`BACKUP.BAK`；20MiB、40,960个512字节扇区，起始绝对扇区`0xc000`。R5 `nflasha6`已识别为gridline／Jiritsu相关存储，保留，不照搬M4分区号。

| 记录 | current／still／movie属性ID或范围 | 目标 |
|---|---|---|
| FL2六槽中的三项 | `02cf0b69`／`02cf0b93`／`02cf0b97` | 均为`0A` |
| FL3六槽中的三项 | `02cf0b6f`／`02cf0b95`／`02cf0b99` | 均为`0B` |
| CC1 `02a40001`映射 | 属性内`0x1236..0x1239` | `[22,24,23,25]` |
| CC1四行有效系数 | `0x1250 + bank×64`，bank22～25各48字节 | 作者转换后的FX2差分系数，保留原格式和其余标定 |
| block13 `02a4000d`映射 | 属性内`0x1cc..0x1cf` | `[22,24,23,25]` |
| block13四bank | 属性内`[0x43e0,0x4fe0)`，共3072字节 | 指定FX2供体矩阵 |
| BK4校验和 | 各段`+0x20`的4字节字段 | 重算该段byte sum，排除自身4字节 |

BIN和BAK两份同时处理；六槽记录必须长度1、属性`0x60`，前值仅接受00或对应目标值。颜色基线、供体、结构均有固定散列及范围核对；其他文件、FAT布局、个人标定、版本文件及升级标志保持原值。

#### 4.2 实际连续部署入口

准备新会话目录并确认相机正常、未更新、两条线已接好后，使用D／T验证过的入口：

```sh
R5_SETTINGS_RUN="analysis/r5_personal_deploy_${R5_SESSION_TAG}"
.venv/bin/python -B tools/run_r5_m4strict_personal.py --port "$R5_PORT" --run "$R5_SETTINGS_RUN"
```

**该命令会复位相机、进入fastboot、执行限定持久写入，成功后正常reboot。** 不另行先进入fastboot，不在备份后停几分钟再接着写。该脚本连续完成：

1. 校验核心源码、工具包模块、pyserial与原始RAM载荷身份，并保存本次执行工具散列。
2. 进入接口后核对协议和分区几何；采集当前SDM2、AP ROM、完整设置logical/raw，与本机首次身份资料比较，并逐扇区独立AES-XTS解密核对。
3. 只读执行3次`oem darwin`，间隔5秒，要求状态稳定；写前再查一次。接受已审查的FF或持续00停走状态，不发送看门狗修改命令；未知／活动／变化状态直接停止。
4. 在新备份上生成候选、正反向稀疏差异和限定写入程序。检查两套BK4解析、六槽、颜色字段、所有非目标文件与FAT布局不变；候选重复处理应幂等。超出64扇区或6600字节的保护上限拒绝，不把上限当每次应写数量。
5. 若候选已经等于当前设置，记`already_target_no_write_needed`，不发送flash并正常reboot；这不是又刷了一次。
6. 写前完整重读设置logical/raw及SDM2，要求与本次刚采集完全一致。检查下载散列和候选未变化，禁止拿历史D／T的patch或restore替代本次生成物。
7. 在同一USB写入进程完整接收已批准的稀疏下载后，只发送一次`flash:nflasha2`，核对设备应答的扇区数与本次差异一致。
8. 完整读取写后20MiB logical/raw及SDM2；logical逐字节等于候选，全部40,960个raw扇区独立解密匹配，raw／logical变化扇区一致，SDM2不变，再核验目标字段和非目标范围。
9. 全部通过保存`readback_verification.json`，才发送正常reboot；用户确认恢复拍摄。完成状态应为`written_verified_reboot_acknowledged`。

会话D为30扇区／3710字节，T为30扇区／3711字节；差1字节与各自设置／校验前态有关。它们是历史结果，不是可盲套到每台机身的固定写入数。

#### 4.3 本次目录必须留存的文件

| 文件 | 用途 |
|---|---|
| `report.json`、`ram_boot/`与各阶段日志 | 入口、时间、接口、执行散列、是否已发送持久写入及reboot结果 |
| `pre.settings.logical.img`／`pre.settings.raw.img` | 当次新读取的写前完整设置 |
| `pre.sdm2.raw.bin`、`pre.ap_bootrom.bin` | 同机身及几何核对资料 |
| `prepared/candidate.logical.img`、`prepared/verification.json` | 当次候选、目标字段与实际差异 |
| `prepared/patch.sparse.img`、`prepared/restore.sparse.img` | 仅绑定本次前置状态的正反向差异；restore生成不代表已执行或随时可回滚 |
| `prewrite.*`、`immediate_prewrite.log` | 发送flash前最后一次完整再读 |
| `flash.log`、`post.settings.*`、`readback.log` | 唯一写入应答及完整设备回读 |
| `readback_verification.json`、`reboot.log` | 独立解密、目标一致性及正常重启应答 |

底层`deploy_r5_m4strict_personal.py`的`acquire`／`prepare`／`write`用于实现上述环节；日常部署使用连续入口，避免手工拆步导致接口超时。`build_r5_m4strict_personal.py`仅生成离线副本，不读设备、不证明输入新鲜，也不能用其输出直接覆盖现在的相机。旧`modify_r5_slot_settings.py`等仅保留被导入的通用函数，不运行其旧独立入口。

### 5．SD更新与正常重启后的只读回查

第4步写后回读发生在reboot之前，只证明“当次写入已落盘”。正常启动后需再次采集，验证六槽和颜色是否保持；同时核查SD更新后的CP存储和WBI。采用I会话成功过的只读入口，另开新目录：

```sh
R5_CHECK_RUN="analysis/r5_postboot_check_${R5_SESSION_TAG}"
.venv/bin/python -B analysis/r5_fl23_st_color_audit_20261016/acquire_readonly.py --port "$R5_PORT" --run "$R5_CHECK_RUN"
```

该脚本载入原固定RAM入口，核实SDM2／AP ROM，读取20MiB设置logical/raw、eMMC `nflasha8`、CP NOR窗口、`nflasha10`和WBI头，最后尝试正常reboot。它不调用prepare／flash；要求报告`state=acquired`、`persistent_write_commands_sent=false`、`normal_reboot_acknowledged=true`后再分析。

| 回查对象 | 通过标准 |
|---|---|
| 设置logical/raw | 完整20MiB；40960扇区独立解密逐字节匹配 |
| BIN／BAK六槽 | 两份均为本节列出的FL2三项0A、FL3三项0B，BK4校验有效 |
| CC1／block13 | 两份完整记录的目标映射和颜色范围等于作者方案；使用`build_image(当前logical)`应不再产生差异 |
| 版本／更新文件 | 4.04状态与本次预期一致；设置部署前后保持非目标文件原值，不能用全区散列跨重启强求所有正常设置字节不变 |
| eMMC CP | 从新读`nflasha8`提取`CPAPP-B.BIN`，完整17,617,008字节及SHA-256等于最终4.04 CP |
| 物理CP NOR | 在已核实布局和字节序后比较同一目标CP；本机I从`0x200000`直接顺序读取后全字节匹配，无需swap16 |
| WBI | 读取头部为目标`WBI3`；不等同于取得拍摄时RAM |
| AP | 完整验收还需新读`nflasha15`并提取`/lib/appFw.so`，完整SHA-256等于4.04 AP；以上只读入口未采集AP，不能声称此项自动通过 |

AP目标SHA-256为`8ee4d5876b7e127df39f8f820b9d21834c300ff895e02ca522636ed4733efc4b`，CP目标SHA-256为`8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32`。AP可参考`read_r5_installed_fl2_fl3.py --port … --output … --partitions nflasha15`在独立新会话采集；该工具使用较早的ready文字判据且最终会reboot，不能嵌入正在进行的连续写入。其旧配套`compare_r5_installed_fl2_fl3.py`固定旧包和旧目录，不作为4.04比较器。

NOR采集脚本固定本机已核实的`0x200000`起点和`0x1100000`窗口，不能直接当另一机身通用布局。eMMC CP匹配不能替代NOR，M4样例的swap16也不适用于本机I记录。

**原`verify_post404_readback.py`是I事故快照核验器：其中断言六槽全00、颜色等于原厂。它不能作为T后“目标设置保持”的通用验收脚本；正确目标0A／0B会被它判失败。** 新回查应按本表目标核验并写入本次新结果，不改旧脚本或旧JSON来适配新状态。

下面是针对上述新采集目录的离线检查命令：只读取已保存文件，要求六槽／颜色已经是目标、CP两处匹配及WBI3；任何断言失败都应调查，不自动修复。它不访问相机，也不将用户启动确认或AP验收写成已通过：

```sh
.venv/bin/python -B - "$R5_CHECK_RUN" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / 'tools'))
from build_r5_m4strict_personal import build_image, Fat
from modify_r5_slot_settings import raw_verify
run = Path(sys.argv[1]).resolve()
acquisition = json.loads((run / 'report.json').read_text())
assert acquisition['state'] == 'acquired'
assert acquisition['persistent_write_commands_sent'] is False
assert acquisition['normal_reboot_acknowledged'] is True
assert (run / 'sdm2.raw.bin').read_bytes() == (root / 'backups/R5_4.00_20261014_full/sdm2_partition_table.raw.bin').read_bytes()
assert (run / 'ap_bootrom.bin').read_bytes() == (root / 'backups/R5_4.00_20261014_full/ap_bootrom.raw.A.bin').read_bytes()
logical = (run / 'settings.logical.img').read_bytes()
raw = (run / 'settings.raw.img').read_bytes()
raw_verify(raw, logical)
assert len(logical) == len(raw) == 20 * 1024 * 1024
target_settings, _ = build_image(logical)
assert target_settings == logical, 'Six slots or author color ranges differ from target'
cp = Fat((run / 'nflasha8.logical.img').read_bytes()).read('CPAPP-B.BIN')
expected_cp = (root / 'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes()
assert hashlib.sha256(expected_cp).hexdigest() == '8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
assert cp == expected_cp
nor = (run / 'cp_nor_00200000_01100000.bin').read_bytes()
assert len(nor) == 0x1100000 and nor[:len(expected_cp)] == expected_cp
assert (run / 'nflasha5.header.bin').read_bytes()[:4] == b'WBI3'
assert Fat(logical).read('UPDATER/DAT4') == bytes.fromhex('0404')
report = {
    'scope': 'Offline verification of saved post-boot acquisition',
    'camera_io': False,
    'settings_logical_sha256': hashlib.sha256(logical).hexdigest(),
    'all_40960_raw_sectors_match_logical': True,
    'six_slots_and_author_color_ranges_are_target': True,
    'emmc_and_physical_nor_cp_match_final404': True,
    'wbi3_and_dat4_0404': True,
    'AP_verified': False,
    'shooting_and_video_verified': False
}
with (run / 'target_postboot_verification.json').open('x') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
PY
```

当前T写后完整回读已通过，U重启后回查未进入接口，故仍缺独立持久性验收。任何设置缺失应基于这次新回读重新生成差异，不回刷首次备份或历史完整设置区。

### 6．实拍验收、停止条件与失败处理

正常启动、设备回读和实际功能分别留证。先确认版本页4.04，再在相同曝光、白平衡及拍摄条件下新拍ST／FL／FL2／FL3的JPG／ARW，保留原片与菜单选择对应关系。核对拍摄界面右侧名称、回放名称和颜色；FL2／FL3 MakerNote预期B020为对应外观，B029分别为22／23，不应继续记录Standard／0。再验证视频、旧外观、关机后重新开机的选择保持；特殊模式及恢复出厂后的行为单独记录，不能用一次普通照片通过代替。

与Edit对照时使用重新显影结果，不看未更新的内嵌预览。用户视觉一致反馈、元数据标记、像素量化分别说明；RAW参数数值相等不能替代机内实际选择与成像证明。

| 发生位置／现象 | 如何处理 |
|---|---|
| 载荷或源码散列不符、分区／ROM不符、设置基线未知 | 停止，不放宽校验、不改未知标定、不写入 |
| 入口未成功、接口消失，`persistent_write_command_sent=false` | 保存本次目录；未写入时可由脚本尝试正常reboot，确认相机状态后再决定新会话，不从旧prepare续写 |
| 只读看门狗状态活动／未知或前后变化 | 写入前停止，不加入看门狗写命令规避 |
| 写前重读与刚备份不同 | 停止；重新采集、分析变化，不使用已生成patch |
| 已发送flash后异常、写后回读不符 | 按`write_needs_assessment`处理，保留现场和所有日志；脚本不自动回滚，也不在此路径自动reboot；按当次前后状态单独判断 |
| SD更新异常、黑屏或0x77灯码 | 保留时间／介质／提示和供电状态；灯码不单独证明分区损坏，不发送无关分区恢复命令 |
| 菜单可选但拍摄显示ST或新照片标记Standard | 先回查六槽／映射与当前程序，不以菜单成功或旧回读证明功能成功 |
| 只有已保存RAW或离线模拟一致 | 记录为离线数学／指令证据，继续独立验收持久性和实拍 |

此流程不包含降级、全盘还原、boot0／boot1重刷、NOR直接写入或自动修复升级中断。原始raw用户区含加密内容及SDM2表，不能当logical镜像刷进某个分区；历史`restore`绑定生成时状态，使用前同样需要新读核对。

完整完成标准是：**当次身份与备份可靠→信任环境匹配→DAT离线核验及机身更新完成→AP／CP／NOR／WBI目标一致→六槽和颜色写后及重启后核验通过→实拍／视频／回放与保持分别验收。** 任一未完成项继续标记待验，不以其它环节通过代替。

## 二、RAW研究与跨机型FL2／FL3证据

### 1．IED与RAW创意外观解锁研究：RAW携带外观参数

Sony Imaging Edge Desktop（IED）／Edit研究发现，兼容Sony ARW的加密SR2元数据中保存了多套创意外观参数。Edit可以读取这些参数，对同一份RAW像素选择不同外观重新显影。

独立“RAW创意外观解锁”工具以原片Standard外观目录为基础，补入FL2／FL3的十个目标字段；原有外观、RAW像素、原片白平衡和其他非目标字段保持原值。处理副本在Edit中可选择新外观，说明这些元数据确实能够参与外观渲染，而不只是菜单名称。

在已对照样片的外观目录中，跨全部外观出现变化的是同一套十个标签；ST与FL之间十项均不同。这里“十个数据块”包括九个数值／二进制字段与一个名称字段，不是十个菜单滑块，也不表示任意两个滤镜都十项全不同——例如FL2与FL3共享780C／780D／780E。

| 参数组 | RAW字段 |
|---|---|
| 三组颜色系数 | 0x7842、0x7844、0x7845 |
| 3×3矩阵及扩展颜色参数块 | 0x7800、0x780F |
| 曲线及附属参数 | 0x7806、0x780C、0x780D、0x780E |
| 外观名称 | 0x7770 |

### 2．FX2、M5、R6的FL2／FL3参数比较

从FX2、A7M5、A7R6原始样片中解密并提取SR2，按同一外观逐项比较TIFF类型、元素数量和完整负载：

- FL2：九个数值／二进制字段严格相等，名称完整负载也相等。
- FL3：九个数值／二进制字段严格相等，名称文本均为FL3；16字节名称负载的最后两字节不同，位于NUL终止符之后，仅作注明。
- 因此，“三机型采用相同FL2／FL3核心外观数值”有直接文件证据；“十个字段所有字节都严格相等”则不符合FL3名称尾部的实际记录。

三机型各使用一张原始样片，结论限于这批数据。FL2与FL3彼此仍是不同的外观，相同指跨机型比较同一种外观。

## 三、固件参数与RAW十字段换算

本表的RAW指解密后的SR2外观字段，不是RAW传感器像素，也不是菜单上的十个调节滑块。

所有索引从0开始。公式中的CC1、block13偏移均相对于对应BK4属性内容；Gamma偏移相对于最终4.04的cpapp-b.bin文件。数组按已验证解析器的小端格式解释。

| RAW字段 | 数据形式 | 对应机内参数 | 机内→RAW换算 | 部署方式／核查结果 |
|---|---|---|---|---|
| 0x7842 | 8×int16 | CC1差分表达第0组 | 每组v：`[v3,v0,v1,v2,2v7,2v4,2v5,2v6]` | 设置区线刷；CP内嵌副本随SD包。逐项一致 |
| 0x7844 | 8×int16 | CC1差分表达第1组 | 同上 | 同上，逐项一致 |
| 0x7845 | 8×int16 | CC1差分表达第2组 | 同上 | 同上，逐项一致 |
| 0x7800 | 9×int16，按行组成3×3 | block13照片bank的group1、slot0，共6项 | 六项展开矩阵，公式见下文 | 设置区线刷；9项逐项一致 |
| 0x780F | 276字节位打包结构 | block13颜色系数、公共分区及控制参数 | 系数区[24,216)按列、相邻槽交换后×4；其余部分见第四节 | 设置区线刷目标bank；完整276字节已分段回放匹配 |
| 0x7806 | 128×int32 | CP照片Gamma内部槽6 | `RAW[i]=2×CP[i]`，i=0..127 | SD卡4.04；128点逐项一致 |
| 0x780C | 1×uint16 | Gamma可选Knee point，空指针走默认512 | `2 × point`，FL2／FL3为1024 | SD部署完整Gamma记录，沿用原厂输出；已回放匹配 |
| 0x780D | 1×uint16 | Gamma可选Knee slope，空指针走默认1024 | `16 × slope`，FL2／FL3为16384 | 同上 |
| 0x780E | 10×uint16 | 原厂Baseband YGain，Gamma可覆盖首项 | 每项×32，FL2／FL3为下述数组 | 沿用原厂表及Gamma默认路径；已回放匹配 |
| 0x7770 | 16字节名称 | 外观名称和枚举 | FL2／FL3名称文本 | 名称支持随SD包；FL3的NUL后尾字节差异仅注明 |

0x780E：`[16384,15616,14976,14208,13568,12928,12160,11520,10752,10112]`。

780C／780D／780E的上述值在FL、FL2、FL3间相同，但不是所有外观都相同：ST的780C=4096、780D=14848，780E首项=17280，其余九项相同。

### 外观与数据位置

| 外观／模式 | CP profile | CC1／block13 bank | CC1有效48字节起点 | block13整bank起点 |
|---|---:|---:|---|---|
| ST照片 | 0 | 0 | 0x1250 | 0x01E0 |
| FL照片 | 41 | 8 | 0x1450 | 0x19E0 |
| FL2照片 | 54 | 22 | 0x17D0 | 0x43E0 |
| FL3照片 | 55 | 24 | 0x1850 | 0x49E0 |
| FL2视频 | 56 | 23 | 0x1810 | 0x46E0 |
| FL3视频 | 57 | 25 | 0x1890 | 0x4CE0 |

CC1属性ID为0x02A40001，block13为0x02A4000D，位于本机nflasha2中的BACKUP.BIN／BACKUP.BAK。视频行仅记录部署位置，本文RAW精确公式验证范围为照片外观记录，不外推视频实时输入。

CC1位置：`0x1250 + bank×64`，每bank有效24个int16，共48字节；不是64字节全部为系数。

block13位置：`0x1E0 + bank×768 + group×192 + slot×12`；每bank有3组，每组16槽，每槽6个int16。本文RAW对应group1，即第二组。

### CC1的正反换算

先统一差分表示：FX2的三组绝对值A、B、C转换成`A、B−A、C−A`；R5目标数据已经是这种表示。三组依次对应7842、7844、7845。

对任意一组机内v和RAW r：

```
r = [v3,v0,v1,v2,2*v7,2*v4,2*v5,2*v6]
v = [r1,r2,r3,r0,r5/2,r6/2,r7/2,r4/2]
```

反算除2在已核对样本中均为整数。若要恢复FX2绝对表示，则把第0组分别加回第1／2差分组；不能把RAW差分数组直接当作FX2绝对数组。

| RAW字段 | FL2照片 | FL3照片 |
|---|---|---|
| 7842 | `[-269,-184,-263,-384,506,712,520,1126]` | `[-269,-189,-51,-448,570,778,566,1126]` |
| 7844 | `[123,-492,151,305,-84,196,-242,0]` | `[0,5,0,0,10,68,-8,0]` |
| 7845 | `[0,-14,118,1,-90,276,-152,0]` | `[0,-207,0,8,-14,196,94,0]` |

CP内嵌FL2／FL3四行与设置区对应四行系数相同，是作者主读取路径使用的副本，不是新增一层独立调色。

### block13到7800矩阵

读取group1、slot0的(a,b,c,d,e,f)，在本批保存元数据的1024对角基准下：

```
M = [a+b+1024,   -a,          -b,
     -c,          c+d+1024,   -d,
     -e,         -f,           e+f+1024]
```

反算：`a=−M01, b=−M02, c=−M10, d=−M12, e=−M20, f=−M21`。该反算对应矩阵还应满足每行和为1024。

| 外观 | 机内六项 | RAW7800，按三行排列 |
|---|---|---|
| FL2照片 | `[-17,-47,-46,113,406,184]` | `[960,17,47]`；`[46,1091,-113]`；`[-406,-184,1614]` |
| FL3照片 | `[138,-221,-42,-128,253,-17]` | `[941,-138,221]`；`[42,854,128]`；`[-253,17,1260]` |

1024基准在本批数值对照中精确成立，不能据此替代所有实时标定输入。

### block13到780F参数块

将group1的16槽记为`q[slot][k]`，k=0..5依次是a,b,c,d,e,f。

```
RAW780F的byte offset = 24 + 2*(16*k+j)
该处little-endian int16 = 4*q[j XOR 1][k]
k=0..5，j=0..15
```

即先输出a列16项，再b、c、d、e、f列；每列槽顺序：

```
[1,0,3,2,5,4,7,6,9,8,11,10,13,12,15,14]
```

反算为对应int16除4，再按同一槽交换顺序放回。192字节系数区完整对应；头24字节与尾60字节在本次所比较ST／FL／FL2／FL3记录间共用，原厂生成来源及完整重建见第四节。

7800和780F来自同一block13颜色组的不同表达。每bank另两组的机内数据不由这两个RAW标签完整描述，不能据此删减作者的复制范围。

### 2026-10-19复核：FX2的B／A1／A2是否搬全

直接读取哈希匹配的FX2原厂供体，并与会话T的实际写后20MiB回读比较；BIN、BAK分别解析，不以构建候选替代写后证据。T快照SHA-256为`f3c3d66e26b612dd7b5a16b66f1d923d21cc00946d0e21984d0e896d6136a34e`。本次没有相机操作，不能推定当前机身RAM或重启后状态。

block13每bank起点为`0x1E0 + bank×0x300`，共768字节：B为`+0x000..+0x0BF`，A1为`+0x0C0..+0x17F`，A2为`+0x180..+0x23F`；每套192字节，16槽×6个int16。最后`+0x240..+0x2FF`为192字节尾部，不能未经消费逻辑证明就称为第四套颜色矩阵。

**我们原方案搬的是四个完整bank，并未仅搬A1。** bank22／23／24／25分别为FL2照片／视频、FL3照片／视频，连续范围`block13[0x43E0:0x4FE0]`共3072字节；T的BIN和BAK这段均逐字节等于FX2，包括B、A1、A2及各bank尾部。映射为`[22,24,23,25]`，按profile顺序对应FL2照片、FL3照片、FL2视频、FL3视频。不是用FL2矩阵代替FL3，也没有遗漏视频bank。

照片slot0六个存储系数(a,b,c,d,e,f)如下；它们需按前述公式展开，不能直接当作六项完整3×3矩阵：

| 外观 | B | A1 | A2 |
|---|---|---|---|
| FL2照片 | `[113,-141,-68,88,128,103]` | `[-17,-47,-46,113,406,184]` | `[225,-242,-80,77,371,-5]` |
| FL3照片 | `[57,-231,81,-255,200,214]` | `[138,-221,-42,-128,253,-17]` | `[225,-265,104,-238,366,-47]` |

三套不是相同数据：FL2照片的B对A1、A1对A2分别有94／96、95／96个int16不同；FL3照片分别95／96、95／96个不同。各套完整16槽数据、视频bank及散列见[本次字节复核](r5_fx2_b_a1_a2_audit_20261019/comparison.json)，脚本为[compare.py](r5_fx2_b_a1_a2_audit_20261019/compare.py)。

CC1同样包含B／A1／A2，但每套是8个int16。FX2以绝对值保存；R5格式为B、A1−B、A2−B。将T快照的差分重新还原后，四个bank的全部24项都等于FX2原厂值；各行尾16字节保留R5，符合当前格式适配边界。block13头部的坐标轴`0x100..0x123`与三个通道基准`0x190..0x195`也已确认R5与FX2相等，未发现这两项共用数据漏搬。

必须区分历史原方案与作者最新方案：我们固定的`086df3b`完整复制原始B／A1／A2；作者最新`a15a0cb`默认`fixed-a1`把每bank自己的A1重复写入B、A1、A2，保留原三端点的方式改为显式`dynamic`研究模式。对当前四个bank改成固定A1，将分别改变189、172、190、192个有效int16，并非“补上缺失的数据”。最新作者还修改了M4相关矩阵选择逻辑，不能据数据存储完整就证明R5实际动态选择与FX2等效，也不能未经R5运行路径核验直接采用固定A1。现有RAW换算对应A1，只覆盖三组中的一组；样片接近Edit不证明其他端点从不参与实际成像。

### CP Gamma到7806

移植共六条完整Gamma记录，将FX2的580字节布局适配为R5的576字节，保留附属参数；不是只复制采样点。Gamma ID扩展至47～50，旧ID0～46表项保留。照片RAW只描述其中一种内部曲线，不能因此删减其他记录。

```
RAW7806[i] = 2*CP_still_slot6[i]，i=0..127
反算CP[i] = RAW7806[i]/2
```

CP有129个u32点，RAW只含前128点；最后一点不能由本标签直接反算。

| 外观／曲线用途 | 最终4.04 CP文件偏移 | 是否对应本表7806 |
|---|---|---|
| FL2照片内部槽0～5共用 | 0xAE74C0 | 否 |
| FL2照片内部槽6 | 0xAE7700 | 是 |
| FL2视频内部槽6 | 0xAE7940 | 本表未验证视频RAW对应 |
| FL3照片内部槽0～5共用 | 0xAE7B80 | 否 |
| FL3照片内部槽6 | 0xAE7DC0 | 是 |
| FL3视频内部槽6 | 0xF76728 | 本表未验证视频RAW对应 |

这里“内部槽6”是Gamma表内部索引，不是用户菜单第六个创意外观，也不是设置区current／still／movie六槽。

FL2前8点：CP=`[0,1158,2316,3474,4632,5789,6947,8105]`；RAW=`[0,2316,4632,6948,9264,11578,13894,16210]`。

### 核验覆盖

R5／FX2各ST、FL、FL2、FL3，共8组：CC1的24个8元素数组、7800的8个矩阵、780F每组96项、7806每组128点，均精确通过上述数值关系。FX2／M5／R6的FL2／FL3九个数值字段与保存R5 RAW对应负载相同，共54项字段比较通过；没有独立从M5／R6固件推导。

R5文件DSC00430／431／432中的对应外观十字段负载互相完全相同，比较以430为主；拍摄／编辑来源未独立认证，只作为保存文件的数学对照。不能据此证明当时机内正确选中bank或未经RAW工具修改。最初完整字节搜索未命中只说明存储编码不同，不能当作缺项证据；旧`evidence.json`保留其原调查范围。

## 四、共用字段的原厂来源与遗漏检查

### 780C／780D／780E

以下使用CP文件偏移；Thumb地址为文件偏移加`0x108000`。

| RAW字段 | 原厂来源 | FL2／FL3换算 | 结果 |
|---|---|---|---|
| `780C` | Knee高光拐点point | 未指定覆盖时`512 × 2` | `1024` |
| `780D` | Knee斜率slope | 未指定覆盖时`1024 × 16` | `16384` |
| `780E` | Baseband十档YGain | 原厂uint16表逐项`×32`，Gamma可覆盖首项 | 见下文 |

模块名称有原厂字符串支持：`PQD_Knee.cpp`、`Cetus/PQD_Baseband_SystemDepend.cpp`、`GetRawParam...IFD of Fader/YGain`。Knee计算代码`0x9a221e..0x9a2246`在超过point后按`(x-point)*1024/slope`计算，支持拐点／斜率的角色判断。这些不是菜单里的十个调整滑块。

Gamma记录的三个指针：

| 记录内偏移 | 原厂载入后偏移 | 用途 |
|---|---|---|
| `+0x228` | `+0x28` | 可选YGain首项 |
| `+0x22c` | `+0x2c` | 可选Knee point |
| `+0x230` | `+0x30` | 可选Knee slope |

原厂加载块为`0x30c05e..0x30c0be`，已在当前Gamma表重定向清单中。逐外观RAW路径的公式为：

```text
780C = uint16(2  * (point_ptr ? uint16(*point_ptr) : 512))
780D = uint16(16 * (slope_ptr ? uint16(*slope_ptr) : 1024))
780E[i] = uint16(32 * base_YGain[i])
若YGain_ptr非零，780E[0]改为uint16(32 * uint16(*YGain_ptr))。
```

R5原厂表位于`0xdbf28c`，FX2对应表位于`0xeb8be0`，十项完全相同：

```text
固件：512,488,468,444,424,404,380,360,336,316
RAW：16384,15616,14976,14208,13568,12928,12160,11520,10752,10112
```

之前直接搜索RAW二十字节没有命中，是因为固件存的是乘32之前的值，不能据此判断缺失。

RAW生成主链为`0x760fb0 → 0x73dd36 → 0x99f70c`，后者调用Gamma载入、Baseband和Knee输出。`0x76110e`／`0x76111c`明确写入780C／D标签；Baseband输出函数为`0x995506`，Knee输出为`0x9a2286`。

#### 与现有移植的核对

当前六条Gamma记录按R5结构适配后完整复制，并非仅复制129个曲线点。核验六条转换后576字节与最终4.04逐字节一致，三个对应指针均为零，与FX2相同；零指针代表有效的原厂默认路径。

对FL2 ID47、FL3 ID48照片内部槽6，执行真实R5 Gamma尾部加载块，再执行真实Baseband／Knee输出函数，三个字段全部与保存RAW逐项相等。没有发现需要再移植一组独立短字段。

FL、FL2、FL3共用上述数值；ST的780C=4096、780D=14848、780E首项=17280，其余九项相同。ST Gamma三个指针非零，支持专用覆盖值的解释；**本轮没有重放ST指针目标的启动初始化**，不称ST来源也已完整回放。

### 780F共用84字节

原厂注册表`0xc07a48`将780F注册为276字节，入口指向`0x13d2e4`。其经`0x622658`处理矩阵，调用`0x624cae`打包。**这是位打包结构，不能把整个字段都当成连续int16颜色系数。**

| RAW字节范围（零基，右端不含） | 来源 | 当前处理 |
|---|---|---|
| `[0,24)` | 16段色相分区坐标、模式／控制位 | 沿用R5公共block13及原厂代码 |
| `[24,216)` | group1的16槽×6系数，按列重排×4 | 已复制FL2／FL3供体系数 |
| `[216,248)` | 16个分区间隔换算系数，配对打包 | 原厂读取函数生成 |
| `[248,276)` | 三通道基准、分区控制字节、末尾控制值等，存在混合字节／位打包 | 沿用原厂配置和默认分支 |

具体来源：

- block13 `+0x100`保存16坐标`0,64,...,960`；`+0x120`为换算位移，值1。
- 原厂`0x12c344`按`(8192 << shift)/interval`生成16个间隔换算系数。本机均为256，RAW中对应重复的1024。
- 原厂`0x12c280`按控制模式读取分区字节及控制值；本次标准照片条件下ST／FL／FL2／FL3均为模式1，分区控制字节均为128。
- 三通道基准在本次路径由默认分支给出`1024,1024,1024`；特殊模式也可读block13 `+0x190..+0x195`，不能称该特殊读取为所有场景的来源。
- 公共参数读取及打包代码与R5原厂逐字节相同，部署没有改变block13 `[0,0x196)`。

R5／FX2整个block13头部存在20字节差异，详见JSON；本次实际涉及字段及输出匹配目标，不支持盲目复制整个供体头部。

#### 完整重建结果

| 保存RAW的外观记录 | 原厂函数生成完整276字节 | 差异字节数 |
|---|---|---|
| Standard | 完全相等 | 0 |
| FL | 完全相等 | 0 |
| FL2 | 完全相等 | 0 |
| FL3 | 完全相等 | 0 |

生成器不再借用RAW前24或后60字节；RAW只用于最后对照。输入为本机保存设置的公共配置及对应bank系数。

### 对现有添加流程的判断

六槽、CC1、block13目标bank／映射由设置区线刷；完整Gamma记录、内嵌CC1及选择路由等由SD包部署；共用配置和参数生成继续沿用R5原厂逻辑。CP内嵌四行CC1是作者主读取路径的同系数副本，不是额外一层调色。

当前block13仅复制供体`0x43e0..0x4fe0`的3072字节及对应4字节映射，不覆盖整个`0x7000`记录；CC1写四行各48字节及4字节映射。BK4校验和是有效性维护，不是颜色效果。六槽及AP look10／11→CP color19／20、profile54～57路由、范围／名称／元数据支持负责选中目标数据。

本轮没有发现共用字段导致流程不完善。先前缺少的是来源证据，现已补证；不需要因此增改公共头部、额外搬运短字段或缩减作者的矩阵复制范围。

## 五、同机型与跨机型色彩差异

### 同机型不同外观

进一步对照4.04 CP及T写后设置快照，并复用已保存的正常路径选择器证据。ST、FL、FL2、FL3在still和movie各自的CC1整行与block13整组都不同，八组间也未找到相同整行／整组。不是每个元素都不同：FL2与FL3照片CC1为24个int16中19个不同；视频为21个不同。每组block13为768字节，照片426字节不同，视频443字节不同。

CP内嵌的FL2／FL3四行系数与各自设置CC1行逐字节相同；FL2、FL3之间及照片／视频之间互不相同。它不是独立的第四套调色模型。

FL2／FL3六条576字节Gamma记录两两不同；每种外观still的内部槽0～5共用同一条，still槽6和movie槽6另用不同记录。六条记录的末尾u32结构字段都为2，不能把这一共同字段误认为整条曲线相同，且字段完整硬件含义尚未确定。ST、FL、FL2、FL3正常路由的对应Gamma记录也互不相同。

该比较没有逐一枚举其余八种外观，不声称全部十二种每对数据都不同。可重跑compare_look_banks.py，仅读取本地文件；完整源散列、逐对相等性及差异数量见look_bank_comparison.json。本次REA拒绝裸CP格式，沿用已有绑定源散列的布局／选择器证据作本地字节比较，没有启动相机或固件。

### R5与FX2的原有ST／FL

比较R5原厂4.00与FX2原厂1.01的同名外观；R5在T写后快照中的这几行CC1和block13已核对保持原厂。先把R5差分CC1还原成绝对系数，再与FX2比较，不把存储格式差异当作调色差异。此处为相同零调节输入下的普通路径，不包含两机实际标定与运行上下文。

| 外观／模式 | CC1有效24项中不同数量 | block13每组768字节中不同数量 | Gamma主曲线129个u32采样点 |
|---|---:|---:|---|
| ST照片 | 14 | 334 | 全部相同 |
| ST视频 | 20 | 318 | 全部相同 |
| FL照片 | 21 | 350 | 全部相同 |
| FL视频 | 23 | 332 | 全部相同 |

Gamma需要区分曲线与完整记录：将FX2的580字节记录按已验证的布局适配成576字节后，FL照片内部槽6和视频内部槽6记录完全一致；FL照片槽0～5共用记录仅+0x21c从R5的5变为FX2的3。ST照片槽0～5也是该单字段差异；ST照片槽6另外三处附属RAM地址字段不同，ST视频槽6一处附属RAM地址字段不同。引用RAM内容和完整效果未采集，不能把地址不同直接说成曲线形状或画面必然不同。

CP新增四行内嵌系数只服务FL2／FL3，不是给ST／FL又移植了四行，因此ST／FL跨机型比较的这一项不适用。本报告没有声称原固件所有代码段均不存在任何常量副本。

129个点为已验证固件消费函数复制的516字节范围，不可直接等同于ARW十字段表中的128元素标签。脚本compare_r5_fx2_st_fl.py与完整证据r5_fx2_st_fl_comparison.json保留原始绝对数值、曲线记录散列、逐字节差异和源文件身份。结果不证明跨机型最终像素相同。

### 数学差距量化

距离统一为norm(FX2-R5)/norm(R5)：CC1用24维绝对系数向量L2范数；block13按已验证的R5读取公式展开为3×3矩阵，采用Frobenius范数。矩阵的两机对角校准基准统一假设为1024，统计每个bank内3组×16槽共48张矩阵；这不是两台相机当前校准测量。

| 同名外观／模式 | CC1整体相对距离 | 矩阵相对距离中位数 | 矩阵相对距离最大值 |
|---|---:|---:|---:|
| ST照片 | 7.96% | 11.36% | 20.31% |
| ST视频 | 20.93% | 9.05% | 18.66% |
| FL照片 | 21.56% | 14.62% | 38.93% |
| FL视频 | 12.18% | 11.10% | 19.10% |

这不是逐项百分比取平均，而是整体差向量／原向量的范数比，避免接近零的单项使相对误差失真。矩阵中位数针对48个表项，不代表实际场景概率或真实插值权重。数据差距超过单纯取整噪声，但没有据此测出最终颜色差距。

统一对角基准时，所有展开矩阵的行和相同，差矩阵每行和为零，因此单独这一数学矩阵对相同中性输入的差为零；彩色输入则可能受不同通道混合影响。此结论不包括CC1、白平衡、传感器标定及其他处理阶段。

离线脚本measure_st_fl_distance.py和完整结果st_fl_numerical_distance.json保留逐项偏差、全部48张矩阵及统一单位输入立方体的代数探针。没有裁剪、Gamma、真实ISP或感知色差计算，不能把系数／矩阵距离直接称为画面百分比差异或DeltaE。

### R5／FX2的RAW对应关系

| RAW字段 | R5 ST对FX2 ST | R5 FL对FX2 FL | R5样本FL2／FL3对FX2同名外观 |
|---|---|---|---|
| 7842／7844／7845 | 不同 | 不同 | 相同 |
| 7800／780F | 不同 | 不同 | 相同 |
| 7806／780C／780D／780E | 相同 | 相同 | 相同 |
| 7770名称 | 全字节相同 | 全字节相同 | FL2全字节相同；FL3文本相同，NUL后尾字节不同 |

CC1差异经过第三节公式精确反映在RAW中。因此“新三机型的同名FL2／FL3相同”不能推为“所有机型同名外观全相同”。

### A1 II样本与R6的FL2／FL3比较边界（2026-10-19）

用户提供`/Users/LOCAL_USER/Downloads/Sony - ILCE-1M2 - 14bit lossless (4_3).ARW`。元数据型号为ILCE-1M2、版本2.00，拍摄时间2025-05-09。格式解析SR2外观指针表共10项，仅有Standard、Vivid、Neutral、Portrait、FL、VV2、IN、SH、BW、Sepia，每项114字段；没有FL2或FL3参数组。ExifTool独立解码的外观列表与结构解析完全一致。

R6参考`DG707670.ARW`则为ILCE-7RM6 v1.01，共12项，含FL2、FL3。因此**这份A1 II样片不足以判断其FL2／FL3是否与R6一致**，不能用已有供体注入后的一致来冒充原生比较，也不能由旧样片缺项推断所有后续A1 II固件均无此功能。要做原生参数比较，需要来自已支持FL2／FL3版本的A1 II原始ARW，并确认其自身带有对应参数组；拍摄时不必选中FL2／FL3，只要原生文件的目录包含它们。

原文件均保持不变，未执行解锁、注入、显影或相机操作。完整文件散列、目录、独立元数据及比较状态见[comparison.json](a1ii_r6_fl23_20261019/comparison.json)，只读复现脚本为同目录[compare.py](a1ii_r6_fl23_20261019/compare.py)。

### 跨代ST／FL的参数关系

对FX2、M5、R5、R6原始RAW的ST和FL进行比较，发现同名外观的颜色参数并不总相同。其中M5与R6在三组CC1对应字段上相同，但不能概括为二者全部ST数据一致。

| RAW字段 | ST／Standard跨机型关系 | FL跨机型关系 |
|---|---|---|
| 7842／7844／7845 | M5＝R6；FX2、R5各自不同 | M5＝R6；FX2、R5各自不同 |
| 7800／780F | 四款样片各不相同，包括M5与R6 | M5＝R5＝R6；FX2不同 |
| 7806／780C／780D／780E | 四款同名外观对应值相同 | 四款同名外观对应值相同 |
| 名称 | 相同 | 相同 |

这表明同样叫ST，颜色系数与矩阵仍可能发生变化；新一代机型也不是所有颜色数据都机械共用同一套。

### 对跨代色彩优化的推测

结合这些参数差异，可以提出一个研究假设：**除白平衡算法等环节外，索尼的部分跨代色彩优化，可能通过创意外观层的颜色系数与矩阵实现，并随RAW元数据交给Edit使用。**

它有参数变化和可替换显影的依据，但目前仍是“疑似”：传感器与机身标定、拍摄条件、其他私有显影参数也可能影响同名外观数据。不能把全部跨代色彩差异都归因于这十项，或断言已定位索尼唯一的色彩优化位置。

### R5使用R6 ST参数的视觉观察

IED项目已生成同一R5 RAW的A／B对照副本，将Standard组的十个目标字段赋为R6 ST数据。实际改变五项：7842、7844、7845、7800、780F；另五项原本已相同。其余104项外观字段、其他11种外观、RAW像素、白平衡、曝光、镜头和预览保持不变。

用户于2026-10-17此前总结时反馈：**在Edit重新显影后，采用R6 ST参数的版本，肤色部分比R5原ST更明亮，整体偏黄有所改善。** 该结果与“同名外观的颜色参数变化能够改变肤色和整体色彩”的假设相符，也说明至少在该对照中，无需改变原始RAW像素即可看到差异。

这里的“肤色更明亮”和“偏黄改善”最初为用户视觉观察。2026-10-17随后对两张ST导出做了独立量化：黄红分量确实减弱，但所选玩偶脸部的数值明度略降，不能把“视觉更清透”直接解释为提亮；详细结果见下节。不要用未更新的内嵌预览或Finder缩略图替代重新显影结果，也不要把这一结论直接套用于整套容器模板替换的“RAW功能解锁”工具——后者还可能继承其他私有字段。

### R5 ST与替换R6 ST参数的JPG量化

用户指定`/Users/LOCAL_USER/Documents/fl对比/DSC00430_ST.JPG`和`DSC00430_ST替换为R6.JPG`。两张均为9504×6336、sRGB、`Edit 4.1.00.03062`导出，同一拍摄时间及曝光／白平衡记录（1/125秒、F2.8、ISO320、5300K）。Sony CreativeStyle／ColorMode仍为原拍FL标签，因此不以这些标签认证Edit重新显影时选择的ST；对照身份以用户确认和保存的参数替换实验为依据。

全分辨率RGB直方图交集均值为**98.948%**、BC分布亲和度均值为**99.985%**，其中R／G／B交集分别98.269%、99.451%、99.125%。亮度码值Y′交集99.299%。RGB全分辨率PSNR为45.17dB；平均绝对误差分别为0.984、0.556、0.705个8位码值。直方图高度相似不能排除局部色彩变化，BC也不是还原准确率。

统一缩至1584×1056后，平均ΔE00全图为**0.505**、主体矩形0.737、彩色主体**1.596**；灰色背景为0.401，主体颜色变化比背景集中。固定矩形均从R5参考图选择，不依据差异大小筛选；彩色主体的掩膜使用R5图中`C*ab>15且5<L*<95`的同一像素集合对照。缩图局部结果如下，差值方向均为R6参数导出减R5参数导出：

| 固定区域 | 平均ΔE00 | ΔL*（正=更亮） | Δa*（负=少红） | Δb*（负=少黄） | ΔC*ab（负=彩度降低） |
|---|---:|---:|---:|---:|---:|
| 高玩偶脸部三块皮肤色 | 1.285 | −0.685 | −1.376 | −1.115 | −1.734 |
| 矮玩偶脸部三块皮肤色 | 1.243 | −0.553 | −1.251 | −0.910 | −1.533 |
| 棕红头发 | 1.817 | −1.293 | −1.635 | −2.539 | −2.810 |
| 青色裙子 | 1.056 | +0.300 | +0.923 | +0.552 | −1.145 |
| 红衣区域（含部分背带） | 1.445 | −1.073 | −1.071 | −1.900 | −1.984 |
| 灰色背景 | 0.401 | +0.023 | +0.068 | +0.112 | −0.095 |

脸部测量另以原分辨率复核：高／矮玩偶分别采样38,076／50,144像素，平均ΔE00为1.365／1.362，平均ΔL*为−0.706／−0.556，Δa*为−1.402／−1.267，Δb*为−1.124／−0.910。与缩图结果方向一致，因此“脸部没有数值提亮”不是由缩图造成。玩偶脸部是涂装塑料，不代表真人皮肤；场景没有标准色卡，也不能据此评判哪套参数更准确。

**本组主要变化为暖色、红黄色的彩度减弱，灰背景基本保留；不是统一提高曝光，也不是整张图一致偏冷。** 例如脸部、头发减少黄红，而青裙的a*、b*向中性靠近并稍亮；变化具有区域／颜色选择性。仅凭JPG还不能把每项变化分配到7842／7844／7845、矩阵7800或780F各自的贡献，更不能把参数替换称作完整R6成像算法复制或原生R6机身实拍验证。

来源复核发现：原始430 ARW仍匹配实验记录的散列；当前R6参数副本比生成时增加1630字节，整文件散列已变化。只在内存重建最初预期副本，散列精确匹配原实验记录，再解析当前副本，确认全部十个ST负载仍匹配R6，各外观负载相对生成时均无变化，保存记录中的RAW像素区域散列全部一致；预览区域及其他私有元数据已有变化。本次未认证这些变化的写入者，也未恢复完整Edit历史，因此JPG测量是当前两张导出的输出差异，不能把所有残差无条件归因于唯一一个参数块。

证据：[直方图](r5_r6_st_comparison_20261017/histograms.png)、[脸部裁切对照](r5_r6_st_comparison_20261017/face_comparison.jpg)、[区域选择](r5_r6_st_comparison_20261017/ROI_selection.jpg)、[完整指标](r5_r6_st_comparison_20261017/metrics.json)、[原尺寸脸部复核](r5_r6_st_comparison_20261017/native_face_verification.json)、[RAW来源复核](r5_r6_st_comparison_20261017/raw_provenance.json)。脚本为同目录`compare.py`、`verify_native_faces.py`、`verify_raw_provenance.py`，使用桌面内置Python及此前保存的色差函数。输入JPG／ARW均仅只读，没有相机操作。

## 六、画面对照与实机验收边界

用户于2026-10-17此前总结时补充实拍观察：**搬运FX2参数后的机内直出照片，与在Sony Edit中使用R6参数转换为对应FL2／FL3外观得到的图像，颜色表现相同。**

这为前述参数同源和数学换算提供了输出端的视觉印证。2026-10-17随后对用户指定的六张JPG进行了独立量化，结果如下；不将“颜色表现相同”写成逐像素完全相等或所有场景都相同。

至此证据顺序为：**RAW研究发现外观参数→三机型同名FL2／FL3核心数值一致→固件移植数据与RAW字段精确换算→用户反馈机内直出与Edit转换颜色一致。** 写后回读另行证明目标设置曾实际刷入；重启持久性和完整功能验收仍按各自日志记录，不从本次视觉结论反推所有项目均已验证。

### 430／431／432与Edit导出的直方图及色差实测

输入为`/Users/LOCAL_USER/Documents/fl对比/`中的`DSC00430.JPG`、`DSC00431.JPG`、`DSC00432.JPG`，分别配对同编号`后期导出.JPG`，用户指定外观依次为FL／FL2／FL3。未使用另两张430的ST实验图。六文件的尺寸均为9504×6336，EXIF均声明sRGB，无内嵌ICC。机内图软件标记为`ILCE-7RM5 v4.04`，导出图为`Edit 4.1.00.03062`；保存的CreativeStyle／ColorMode均对应FL、FL2、FL3。每对曝光记录均为1/125秒、F2.8、ISO320、5300K、曝光补偿0，拍摄时间匹配；这些记录不能代替完整Edit调整历史认证。

全分辨率计算每通道256档归一化直方图及RGB逐像素误差。色差计算先以同样的LANCZOS算法缩为1584×1056，再按sRGB→XYZ D65→Lab D65计算CIEDE2000，参数均为1；实现对照四组公开Sharma参考值通过，误差小于0.0001。没有曝光修正、直方图匹配或几何变换。792×528的边缘位移诊断在横纵±3像素搜索范围内，三对均以零位移最优，相关系数0.9967～0.9976；这不等于证明亚像素完全对齐。

| 配对外观 | RGB直方图交集均值 | RGB分布亲和度BC均值 | 全图平均ΔE00 | 全图95百分位ΔE00 | ΔE00<2的采样点 | 彩色主体平均ΔE00 |
|---|---:|---:|---:|---:|---:|---:|
| 430／FL | 94.42% | 99.67% | 1.000 | 1.981 | 95.12% | 0.887 |
| 431／FL2 | 95.54% | 99.75% | 1.005 | 2.021 | 94.85% | 0.912 |
| 432／FL3 | 95.84% | 99.80% | 0.962 | 1.881 | 96.20% | 0.966 |

直方图交集为`Σmin(p,q)`，BC为`Σ√(pq)`，再乘100；均为归一化分布指标，不能解释为“准确还原率”或相同比例的像素完全一致。直方图忽略空间位置，因此另列对应位置的ΔE00。色差约1通常属于很小差别，但可见程度依赖显示、区域和观看条件；此处为缩图色差，不代表原尺寸每个细节像素的色差。

灰色背景占比较大，因此另做固定主体矩形和颜色掩膜复查。矩形范围为归一化坐标`x=0.32～0.70，y=0.24～0.99`，占全图28.50%；三组该区域平均ΔE00分别为1.039、1.040、1.035。彩色主体只使用矩形内机内图`C*ab>15且5<L*<95`的像素选择掩膜，两张配对图使用同一掩膜，不按差异大小筛选；分别覆盖全图4.91%、4.16%、4.63%，对应表中最后一列。局部统计仍未显示FL2／FL3独有的大幅色彩误差。

Edit相对机内图的全图平均ΔL*分别为−0.332、−0.258、−0.225，均稍暗；平均Δb*为−0.580、−0.592、−0.537，全图平均稍偏蓝／少黄。其幅度较小且三组方向接近，不能外推所有彩色区域均偏冷。全分辨率RGB平均绝对误差，合并三通道后分别约1.764、1.484、1.517个8位码值；PSNR为40.12、41.25、41.53dB，明确说明输出并非逐像素相同。残差可能涉及显影、降噪、锐化或JPEG编码，本次没有隔离其各自贡献。

**本组结论：FL2／FL3机内直出与对应Edit导出在整体分布及主体颜色上高度接近，差异与原生FL的机内／Edit差异处于相近量级；没有发现新增外观特有的明显色彩失配。** 这是单场景照片的输出端量化印证，不替代跨光源／肤色／饱和色／高动态场景、视频、重启后持久设置或全部原功能验收，也不由文件名及EXIF倒推出样片对应某次部署的运行状态。

复现脚本：[compare.py](r5_fl_edit_comparison_20261017/compare.py)。运行使用桌面内置Python（包含Pillow及NumPy）：

```sh
/Users/LOCAL_USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B analysis/r5_fl_edit_comparison_20261017/compare.py
```

原始输入未修改，无相机操作。六文件散列、完整直方图、全图及局部指标见[metrics.json](r5_fl_edit_comparison_20261017/metrics.json)，元数据见[metadata.json](r5_fl_edit_comparison_20261017/metadata.json)。另保存[直方图叠加](r5_fl_edit_comparison_20261017/histograms.png)、[配对缩略图](r5_fl_edit_comparison_20261017/contact_sheet.jpg)、[主体矩形](r5_fl_edit_comparison_20261017/subject_region.jpg)及逐对ΔE00热图（固定0～5，蓝→黄→红），后者不能按显示颜色当作原图色彩。

### 实机状态按时间区分

- 会话D在SD升级前写入30扇区、3710字节，完整回读通过，用户确认正常拍摄。
- 会话I在4.04后只读回查：六槽全00、CC1／block13等于原厂；eMMC和物理CP NOR完整匹配目标4.04，WBI3。该快照解释了当时选FL2／FL3却显示／记录ST的异常；丢失时点仍未确定。
- 会话T随后使用D原脚本重新部署30扇区、3711字节，六槽0A／0B、颜色字段、20MiB逻辑回读和40960个raw扇区解密核验通过；正常reboot后用户确认恢复拍摄。
- T之后U未进入fastboot，没有新数据或持久写入。I全00不是T后的当前值。用户后续视觉对照作为单独观察记录，不能替代重启后设置回查、全部场景／视频功能验收。

## 七、证据、复现与限制

### 原始证据入口

| 内容 | 脚本／结果 |
|---|---|
| CC1与RAW | [compare_raw_and_cc1.py](r5_fl23_arw10_vs_firmware_20261016/compare_raw_and_cc1.py)／[raw_vs_cc1_correspondence.json](r5_fl23_arw10_vs_firmware_20261016/raw_vs_cc1_correspondence.json) |
| 矩阵与Gamma | [map_matrix_gamma.py](r5_fl23_arw10_vs_firmware_20261016/map_matrix_gamma.py)／[matrix_gamma_correspondence.json](r5_fl23_arw10_vs_firmware_20261016/matrix_gamma_correspondence.json)／[matrix_gamma_probes.json](r5_fl23_arw10_vs_firmware_20261016/matrix_gamma_probes.json) |
| 同机型外观差异 | [compare_look_banks.py](r5_fl23_arw10_vs_firmware_20261016/compare_look_banks.py)／[look_bank_comparison.json](r5_fl23_arw10_vs_firmware_20261016/look_bank_comparison.json) |
| R5／FX2与数学距离 | [compare_r5_fx2_st_fl.py](r5_fl23_arw10_vs_firmware_20261016/compare_r5_fx2_st_fl.py)／[r5_fx2_st_fl_comparison.json](r5_fl23_arw10_vs_firmware_20261016/r5_fx2_st_fl_comparison.json)；[measure_st_fl_distance.py](r5_fl23_arw10_vs_firmware_20261016/measure_st_fl_distance.py)／[st_fl_numerical_distance.json](r5_fl23_arw10_vs_firmware_20261016/st_fl_numerical_distance.json) |
| 共用字段、原厂指令回放 | [audit_common.py](r5_fl23_common_fields_20261017/audit_common.py)／[audit_results.json](r5_fl23_common_fields_20261017/audit_results.json)／[native_ranges.txt](r5_fl23_common_fields_20261017/native_ranges.txt) |
| REA及代码摘录 | [Knee／Gamma bundle](r5_fl23_common_fields_20261017/rea_knee_gamma_bundle.json)／[block13 bundle](r5_fl23_common_fields_20261017/rea_block13_bundle.json)；同目录保留`make_excerpt.py`、ELF摘录及`excerpt_manifest*.json` |
| 实机设置与回读 | [会话D](r5_m4strict_personal_flash_20261015_D/README.md)／[会话I](r5_fl23_post404_readback_20261016_I_poweron/README.md)／[会话T](r5_fl23_post404_redeploy_20261016_T/README.md)／[会话U](r5_fl23_post404_persistence_20261016_U/README.md) |
| 430／431／432机内与Edit量化 | [compare.py](r5_fl_edit_comparison_20261017/compare.py)／[metrics.json](r5_fl_edit_comparison_20261017/metrics.json)／[直方图](r5_fl_edit_comparison_20261017/histograms.png) |
| 430 R5 ST／R6 ST参数导出量化 | [compare.py](r5_r6_st_comparison_20261017/compare.py)／[metrics.json](r5_r6_st_comparison_20261017/metrics.json)／[RAW复核](r5_r6_st_comparison_20261017/raw_provenance.json) |

主要输入SHA-256：

| 输入 | SHA-256 |
|---|---|
| 最终4.04 CP，`build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin` | `8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32` |
| 原厂R5 CP | `3269bf62426339791fcfbe8529698cd4accbe6c3d2ea61cd7c368a90ab7ee7c8` |
| 原厂FX2 CP | `eba723db657117a36d9593dacf640840aca893c0d6ee5d728de9d1996b8c5e29` |
| 会话T写后设置logical | `f3c3d66e26b612dd7b5a16b66f1d923d21cc00946d0e21984d0e896d6136a34e` |

### 共用字段复现与REA记录

运行保存脚本：

```sh
.venv/bin/python -u analysis/r5_fl23_common_fields_20261017/audit_common.py
```

`audit_results.json`含源散列、六条Gamma整记录核验、原厂代码不变检查、CDE输出及四组完整780F。`native_ranges.txt`保存关键指令。`make_excerpt.py`生成不可刷写的ELF摘录，`excerpt_manifest*.json`绑定CP源散列及范围。

本机Unicorn在沙盒内映射内存以132退出；经批准在沙盒外运行保存脚本后全部通过。这是主机模拟环境限制，不是相机故障。

| REA分析 | Evidence ID |
|---|---|
| Knee RAW输出 | `ev_8d87da99d8bd370efbad7b370a99e01fcaf6b686f09ef938793e0290791bc2e6` |
| Baseband YGain | `ev_e8314aa347aae5923894553fe02030cbea6be6ea7785a3b48cb002e3cc496198` |
| Gamma RAW编排 | `ev_6a152ce4fc9578e14a70a3ad19e8635ddeb81d5fbd03b304d6f59d420534aa0e` |
| RAW780C／D写入 | `ev_fc84cb544499eb28696ad10df3dbb4e9bda5b393f6261a7a3a9dc80e3b33dae3` |
| 公共参数读取 | `ev_984fbe77b711e70d3ae753f721a5140f7283d873c455fa648d3218b5d31cbf39` |
| 780F完整打包 | `ev_7b4833c507d20c2383e056cc29c381b8e492cf220f7a827db70e755c79145ef1` |

完整记录保存在两个`rea_*_bundle.json`中。摘录缺少外部断言目标，部分伪代码显示`halt_baddata`或截断；结论同时核对原始ARM字节和独立Unicorn回放，不将摘录伪代码当完整源码。

### 验证边界

- 使用合成运行结构、分段真实指令回放，不是相机执行。Gamma尾部加载及CDE生成实际执行，但未模拟整段OS生命周期。
- 原有选择器测试边界早于公共头部函数；脚本独立调用真实头部读取及控制选择函数，未把A5哨兵当作相机数据。
- RAW打包上下文字段相对选择器输出偏移高`0x24`，脚本显式投影。中间完整服务传递及白平衡／矩阵处理未连续执行。因此这是原厂读取＋原厂打包的分段重放证明。
- 内存清零辅助函数按调用约定替代，原厂断言触发则失败。
- 保存R5 ARW的拍摄／编辑来源未独立认证，只用作数值对照。
- 会话T是最后成功写后回读；较早I的全00不是T后的已知状态。本轮没有采集新实机状态，重启保持及完整成像验收仍须单独报告。

### IED研究与实拍观察来源

- [独立RAW创意外观工具说明](/Users/LOCAL_USER/Documents/ChatGPT/ied软件/RAW创意外观解锁/使用说明.md)。
- [FX2／M5／R6外观参数对照](/Users/LOCAL_USER/Documents/ChatGPT/ied软件/研究记录/20261016_FX2_M5_R6外观参数对照/对照说明.md)。
- [FX2／M5／R5／R6的ST／FL对照](/Users/LOCAL_USER/Documents/ChatGPT/ied软件/研究记录/20261016_FX2_M5_R5_R6_ST_FL对照/对照说明.md)。
- [R5替换R6 ST十项的测试说明](/Users/LOCAL_USER/Documents/ChatGPT/ied软件/研究记录/20261016_R5替换R6_ST十项/测试说明.md)与[逐字段校验记录](/Users/LOCAL_USER/Documents/ChatGPT/ied软件/研究记录/20261016_R5替换R6_ST十项/替换与校验记录.json)。



### 2026-10-21：RAW照片预览取消Edit实时采集

工作台支持LUT目标／拟合结果计算函数／手动导入软件输出三栏对照。按用户最新要求，照片预览只用本地LibRaw解码RAW，不创建或启动Edit副本、不运行Frida。两图共用线性去马赛克数据；LUT复用RawAlchemy颜色参考函数，拟合结果复用测试色块的color_only，但其RAW前端改用拍摄白平衡和历史参考绿色增益近似。既有拟合数据与历史实采证据保留只读，不改固件、原片或导出配方。

前端未模拟Edit的ITP／Vatr／SSCS、降噪、镜头补偿和场景相关增益；LUT去马赛克也不等于RawAlchemy RCD。两图差异包含前端近似误差，不能直接当作参数拟合误差。已验证全尺寸R5原片按16像素间隔生成593×395预览，统一8位、不额外扣黑、未应用EXIF旋转。第三栏软件导出图由用户手动本地导入。14项回归及原片离线渲染通过，最终颜色精度仍未验收。



### 2026-10-21：灰阶优先拟合

用户反馈灰阶差距大并要求第一优先级。原四组等权及综合色差候选选择会牺牲灰阶；当前适配器改为训练数据初始化颜色、灰阶专项优化（保留初始化颜色响应避免色相失控）、灰阶16倍联合损失与灰阶误差约束。最终只在最佳整数模型灰阶RMSE + 0.25个真实8位码值内选综合色差；验证集仅用于候选评估，独立测试不参与选择。双方实际uint8量化后评估、不扣黑。保留全部128个RAW Gamma节点、零点固定，不增加补偿矩阵或网格。

同一LUT、同一数据80次评估，新任务971cfa616f144ce192039d97aa96a7af：灰阶训练RMSE 5.314→3.339，P95 13→7，独立随机测试RMSE 7.821→8.747；灰阶优先有彩色误差取舍，不能称全面精度提升。最亮灰阶前端已为等通道，当前模型保持中性，无法重现LUT高亮染色；纯黑输出仍固定0而目标约7.54/255。这些是当前参数结构限制，不通过修改目标掩盖。旧任务未改写。证据见research/r5_custom_lut/evidence/web_gray_priority_20261021/comparison.json，15项回归及严格配置转换通过；没有Edit实时采集或相机操作。



### 2026-10-21：Web PC 补偿网格

用户授权先增加PC补偿并在Web支持。新增web/pc_compensation.py，复用历史residual_grid.py的5×9×9、405节点、每通道7位残差网格；使用明确暂定的BT.601 limited坐标和单位RGB响应，在原生颜色子链输出后相加。该坐标／响应未标定为R5 ISP，不宣称与QAQ机内渲染相同。灰阶优先训练权重沿用当前方案，只有train样本用于网格求解，不用valid/test选参数；输出参数绑定原LUT、配方和pairs散列。

页面支持已完成任务另行拟合PC补偿、开关切换色块／灰阶／24色／分区误差和直方图、新RAW预览应用同一补偿、独立JSON下载；原生BIN与fitted-ST.ARW仍不包含补偿。原片预览仍为不启动Edit的近似前端。任务971cfa616f144ce192039d97aa96a7af：灰阶训练RMSE3.339→1.308，独立随机测试8.747→5.883，验证9.004→5.969，均为双方真实8位量化、不扣黑。改善仅证明PC暂定模型的本数据效果；后置补偿无法恢复原生处理已合并的颜色。16项适配回归、网页拟合及切换、JSON下载和RAW补偿渲染通过；证据见research/r5_custom_lut/evidence/web_PC_compensation_20261021。无相机操作、固件变更或Edit实时采集。


### 2026-10-21：参考 Cobalt 分层思路的 PC 三阶段补偿

用户同意按公开技术思路改进。核对 Cobalt 官方 https://www.cobalt-image.com/tutorials/our_technology/ ，可借鉴相机校准、ToneCurve、LookTable／HueSatMap 分层；未取得商业求解器源码，不称复现 Cobalt 算法。当前改造只在 PC 原生颜色子链之后运行：①129节点单调编码亮度曲线；②独立RGB零编码亮度染色残差曲线；③5×9×9有界、邻接平滑彩色网格。前两阶段只用256个train灰阶，网格只用原训练样本及固定组权重。按实测合成传感器灰阶轨迹的色度距离保护灰阶：2/255半径内网格为零，8/255范围平滑过渡；灰阶轨迹并不等于实拍白平衡中性轴。各阶段保留浮点值，最终统一裁剪和真实8位量化，不额外扣黑。

新增PC schema /2，保存曲线、网格、阶段指标、来源散列；兼容/1旧网格，升级前按内容散列留存旧JSON，原生配方／BIN／ARW不变。Web支持阶段表、明暗和RGB染色曲线、完整参数下载，色块／灰阶／直方图／新RAW预览共用同一apply函数。预览绑定PC参数SHA，旧补偿预览不冒充新结果，渲染期间参数变化时拒绝结果。新增各输出分区的显示sRGB D65 Lab下ΔE00、L*误差、a*b*误差；使用双方相同8位量化。色差数学复用原compare.py并通过四组Sharma参考值。此为显示解释，不是物理相机色度标定，尚未将ΔE00作为优化目标。

固定任务971cfa616f144ce192039d97aa96a7af：原生／旧PC／新PC灰阶训练RGB RMSE=3.3387／1.3080／0.4579；独立740随机测试=8.7469／5.8827／5.6058；验证=9.0044／5.9687／5.8299。旧PC→新PC灰阶L* RMSE 0.3991→0.1258、a*b* RMSE 0.9293→0.4351。独立测试平均ΔE00旧PC2.7239→新PC2.7625略升（原生3.7207），不能称所有指标改善。前两阶段后灰阶与最终灰阶RMSE相同，网格未破坏该训练轨迹。全部结果只报告固定数据，不作为新数据全局精度验收。

19项回归通过，含篡改valid/test目标不改变曲线和网格、来源绑定、旧schema兼容、单调／零亮度染色、保护灰阶及色差标准值。网页按钮、开关、下载和窄屏曲线验证通过；DSC00430原片通过HTTP生成593×395双图，原片散列不变、Edit运行时未调用。证据research/r5_custom_lut/evidence/web_PC_staged_20261021/comparison.json、pc_before.json、pc_after.json、raw_preview.json及源码快照。

本轮尚未取得实拍双光源／多曝光物理色卡，未新增双光源插值、相机基础标定或校正照片前端近似；未把补偿移到原生裁切之前，不能恢复已合并颜色。不修改4.18机内协议、历史执行源码或原始资料，无相机操作。


### 2026-10-21：原生分阶段拟合与可选 PC 补偿融入整体训练

用户要求前面原生参数也使用分阶段思路、开关放在导入LUT后、结果不再独立模块展示。原生适配器新增只优化128节点共用Gamma的灰阶编码亮度阶段，固定Gamma的CC1／block13色度阶段，灰阶优先与联合微调保留。加入原始单调起点和明暗专项起点的训练误差选择，避免专项亮度曲线成为较差颜色初始化。原生限制未变：零起点、共享Gamma以及中性保持矩阵不能凭空生成任意染色。

开启PC后，训练中每个整数原生候选均从train重新求解PC曲线／网格，验证集评价完整链路；两轮交替步骤固定PC更新原生，再按精确整数模型重建PC。候选灰阶约束和综合色差都作用于最终补偿链路；求解仅train、验证仅选候选、独立test仅最终报告。最终PC从所选配方生成，验证／灰阶RMSE与训练所选候选逐值一致。不是一次性后置追加，也不是联合梯度优化所有网格节点；是明确的分块交替求解。独立原生配方不写PC字段，来源绑定保持。

页面LUT导入后提供“启用 PC 色彩补偿，融入整体训练”，未勾选时也使用新版原生分阶段；移除单独拟合PC按钮和独立补偿卡片。一次开始拟合自动完成整条链路，统一测试色块结果区可切换原生／原生+PC，训练阶段和补偿曲线折叠展示。完整任务ZIP同时包含原生BIN、配置、PC JSON（若开启）、配方和日志。BIN及验证ARW仍仅含原生参数，补偿仍是PC功能。

固定旧任务同一LUT、pairs散列的新网页80评估任务87522a62b7f643b4b621a6b485b88a83：整链独立测试RGB RMSE4.4080、平均显示ΔE00 2.2398、灰阶训练RMSE0.4002；上一版先原生后独立PC为5.6058／2.7625／0.4579。验证RMSE4.6979，所选第二轮交替。其原生单独输出测试RMSE8.7212、灰阶训练3.8901，训练为整链分担误差，不能把补偿后指标标为机内指标。20评估网页流程任务6a2f2d0dc2bc4707b549e2207eaafaa4也自动完成：5.2526／2.3454／0.4177。独立原生关闭PC的80评估回归选gray-priority-joint：测试RMSE8.8933、灰阶训练3.2604；相较旧原生8.7469／3.3387有取舍，并非所有原生指标改善。

21项回归通过，包括开关传入求解器、自动生成并持久化PC、界面无独立PC模块、旧版兼容与train隔离等。网页实际导入LUT、开关、完整训练、整链与原生切换通过；HTTP任务ZIP内容与候选最终指标一致性通过；最终任务DSC00430离线双图渲染通过，原片不变、无Edit采集。证据research/r5_custom_lut/evidence/web_integrated_training_20261021。仍无新增物理双光源／多曝光数据，RAW前端近似限制不变；无相机操作、固件或原始证据改写。


### 2026-10-21：三通道残差只读诊断与离线网格实验

用户截图三通道独立测试RMSE3.5924／5.3819／4.0522、直方图重合67.027／70.541／64.865%，对应ad814c244930405ab29bab73f8e68d05，与87522任务相同输出。绿色误差集中中间调（137样本G RMSE10.0785；阴影595样本G3.4859），不是绿色直方图重合最高就表示更准。网格系数触边比例0，无幅度上限证据。14位碰撞样本占2.30%，该测试集碰撞不可约MSE1.63e-9，不支持把主要误差归因为已合并颜色。

仅在独立新证据目录实验，不改配方、PC JSON、网页或历史任务。第一组固定5种亮度坐标（旧BT601 limited／全幅亮度1／.75／.5／.33次幂），按valid选择，旧坐标最优；暗部坐标加密未改善。第二组保留原生配方、灰阶明暗和染色曲线及灰阶门控，只改PC网格与平滑：固定形状5x9x9、9x17x17、17x17x17，平滑.001／.01／.1，分别保留7位量化和浮点系数，共18候选。只用train求解、valid选候选，选后才报告test。最佳valid为9x17x17、strength .001、浮点系数，valid RGB RMSE3.1070；同形状量化为3.1242，量化收益较小；17x17x17浮点最佳3.2781，更多节点没有更好。

选后独立740测试：通道RMSE2.9201／3.3178／2.9667，总RGB RMSE4.4080→3.0734，平均显示ΔE00 2.2398→1.6873；灰阶训练RMSE0.4002完全不变。具体分区和直方图见dense_probe.json。形状与正则联合调整，不能单独把改善归因于节点数。此为固定数据离线可行性结果，未集成整体交替训练、新数据或RAW照片未验收，不是机内参数精度提升；PC浮点系数不兼容当前机内格式。当前网页与生产PC参数未改，未执行相机或Edit操作。证据research/r5_custom_lut/evidence/web_channel_probe_20261021，包含脚本、候选指标、浮点系数。

### 2026-10-21：撤回灰阶额外权重与优先门槛

按用户要求，将灰阶组总平方损失权重从随机组的16倍恢复为1倍；随机、正色、256级灰阶、CC24四组总权重相等（不是每个样本等权）。移除最佳灰阶RMSE加0.25码值的候选硬门槛，联合阶段与最终选择均按等权综合色差选优；灰阶专项阶段保留为可被淘汰的候选，分阶段流程、PC灰阶曲线与网格灰阶保护保持。旧任务及原始证据不改，新任务生效。

21项回归通过，额外核验CC24总权重一致。2次评估的小规模PC整体训练走完，配方gray_priority=false、四组权重均1，最终候选确为最低等权综合分；仅验证流程与策略，不作为精度改善结论。本地服务在确认无运行任务后重载。证据research/r5_custom_lut/evidence/web_equal_weights_20261021；首次试跑因capture路径错误未进入训练，日志保留，正确路径试跑为smoke_fit2。无相机操作、固件或历史任务改写。

### 2026-10-21：大网格训练压缩与四组权重控制

按用户要求，将“5*99”按前文5×9×9实现。PC每个原生整数候选同时求解原有直接小网格与17×33×33（18,513节点）浮点教师；教师使用train、邻居平滑.001和稀疏LSMR，系数裁剪至既有残差范围。使用25³=15,625个均匀RGB合成查询加train密集采样教师输出；train与查询各占一半总质量，以实际灰阶门控、三线性插值、受限最小二乘压缩到405×3个7位系数。两条路径按相同候选分数比较，最终只保存5×9×9，保持1215字节payload、既有渲染与RAW预览。大网格仅训练中使用，不是新增机内网格或ISP校准。教师迭代上限2000、atol/btol1e-6，若达到上限记录converged=false，候选仍须验证选优；不宣称全局最优。

首轮严格1e-7/600次试跑未收敛，保留失败证据后提高迭代预算。2次评估整体试跑通过，直接小网格最佳等权综合分5.7367、压缩候选最佳7.0830，本数据并未显示压缩收益，最终保留直接路径。两种策略分别重建导出均逐值复现训练候选validation/gray RMSE；不把此小预算试跑当作精度验收。真实HTTP任务e74d1b5089f74b409d234e95c79262a7完成，23项回归通过（包括任意网格插值与现有运行时一致、教师零残差、pack/unpack）。证据research/r5_custom_lut/evidence/web_grid_compression_20261021。

后续用户要求加入权重。新增随机色／正色／完整灰阶／CC24四组总平方误差权重，默认1／1／1／1，允许0.05–64，支持恢复等权。共享校验拒绝缺字段、bool、非有限数与越界；前后端、CLI、配方元数据一致。权重用于原生联合残差、直接PC拟合、教师训练、压缩的实测train部分、整链候选综合分；灰阶专项初始化及tone/tint仍独立求解，只作为可淘汰候选或明确的PC分块阶段。验证随机组与训练锚点按相同总权重选候选，独立test不参与。最终PC重建读取任务保存权重与选定策略，避免配置不一致。历史任务不改，原生关闭PC仍支持同样权重。

非等权1／2／3／4的小规模整体训练与导出检查通过，全部候选分数独立重算一致、所选候选为最低分、最终PC验证及灰阶指标复现。25项回归通过、JS语法通过，浏览器权重控件与恢复等权实测通过。证据research/r5_custom_lut/evidence/web_weight_controls_20261021。权重不是新增信息，不保证所有指标同时改善；更多算力仍受原生模型与最终405节点表达能力限制。未引入神经网络或宣称更换为全局最优算法；无相机、Edit采集、固件及原始RAW改写。

### 2026-10-21：多起点、训练动态权重、感知损失与量化微调

用户要求一并加入。新增optimizer_policy.py，默认4起点（原两种单调起点加固定种子平滑扰动）、动态3轮、感知权重.35、量化1轮；网页分别可设2–12、0–8、0–2、0–3，API/CLI严格校验。扰动包含CC1、平滑色相系数和Gamma对数增量，保留零点单调参数化。所有梯度优化只读取train。每轮依据当前候选精确整数模型的train分组误差，对基础权重乘sqrt(error/median)，限制.5–2倍并维持允许范围；以基础权重为锚点而非累乘，防失控。每轮PC重新求解并记录训练权重。最终候选用固定基础权重比较，动态不能改变排名标尺；独立test仅末尾报告。

联合连续求解加入sRGB/D65 Lab76残差，不在梯度阶段uint8取整。最终选优使用真实uint8 RGB MSE + 感知权重×(2.55×CIEDE2000)²，各组仍按固定用户权重合成；页面显示验证RMSE、ΔE00及固定综合评分。感知项是显示模型，不是相机实测色度校准。权重为0时退回RGB评分。

新增train-only精确整数坐标搜索：8个CC1、96个block13系数、127个非零Gamma节点逐项正负邻域；保持原始低位、块结构、Gamma零点与单调。PC冻结评估原生修改，修改后再重建PC。按4.18导出的Gamma/CC1增益半单位回环对齐，Gamma首轮16原始单位、后续2；block13沿实际非对称量化步距。PC最终405×3个7位节点也逐项±1，目标含uint8与DE00，只接受严格降低train目标的修改；最终仍与未微调候选共同选优。全部点位被遍历，但有限轮坐标搜索不是全局最优。候选保存实际参数与其权重／PC量化轮数，最终导出按所选候选重建，不误用最后一轮状态。

新增历史让JSON超过冻结转换器128KiB限制：Web适配器保留原始完整配方，仅为转换器生成不含fitting诊断字段的紧凑副本，source/parameters原样；审计同时记录两个散列，未修改冻结转换器。测试覆盖原配方不变与参数一致。

31项回归通过，含动态界限与复现、多起点确定性、连续损失梯度、真实uint8+DE00量化目标下降、Gamma/CC1回环、API传参和大配方投影；PC关闭的原生小规模训练也通过。2次评估PC整链试跑所选integer-refinement-PC/direct，原生离散78次接受，训练目标131.984→119.970；原生BIN与PC重建复现所选验证／灰阶指标，独立test RMSE4.1944、平均DE00 2.1230。该早期试跑在随后明确偶数回环对齐前完成，不能代替最终HTTP验收。

同一LUT／数据20评估对照：旧设置（2起点，无动态、无感知／量化）test RMSE4.4667、平均DE00 2.2527；默认新设置test RMSE4.7823、平均DE00 2.2314。感知略降但RGB变差，不能称全面提精度；小预算、固定数据结论，不证明多起点／动态／量化各自因果贡献。比较与精确重建见comparison20.json；20评估也是偶数回环明确前的版本。最终版本含回环对齐与相应测试。证据research/r5_custom_lut/evidence/web_advanced_optimizer_20261021。无相机、Edit采集、固件或原始证据改写。


最终HTTP验收任务b154900317c34e1f979d3cdcadfa9249完成，3起点／动态1轮／感知.35／量化1轮，使用用户权重1／2／3／4；原生BIN和PC输出完成，验证／灰阶指标复现，所选候选为固定评分最低者，原生量化审计包含4.18回环；见http_verification.json与http_result.json。

### 2026-10-21：PC RGB 独立曲线实验选项

应用户要求，Web新增PC曲线方案：现有“明暗曲线 + 灰阶染色”保留；新增“RGB 独立曲线”，在原生颜色子链输出后对R/G/B分别拟合129点单调输入→输出曲线，并可独立关闭5×9×9颜色网格。RGB曲线使用全部训练色块和任务权重，训练与最终PC重建保持相同模式；曲线值、模式与网格开关写入配方／PC JSON。PC模式是电脑模拟输出，不拆分R5原生共用Gamma，不进入R5NATIVE.BIN或验证ARW；页面与报告明确标注。

独立曲线渲染先按通道输入查表，再按可选网格处理；启用网格时继续使用灰阶保护门控。图表在RGB模式显示三条输入→输出曲线及相对恒等偏移，不再误标为共用灰阶曲线。兼容旧tone-tint PC JSON，模式／pipeline不匹配会拒绝加载。

33项回归通过，覆盖独立曲线129节点单调性、无网格零系数、RGB+网格量化微调、PC pipeline校验、API选项传递与旧流程。无网格小规模试跑能导出并复现验证／灰阶指标；同一数据下仅RGB曲线独立测试RMSE12.879、平均DE00 8.025，说明三条曲线不能替代局部颜色网格。已重载本地服务。证据research/r5_custom_lut/evidence/web_rgb_curves_20261021。无相机、Edit采集、固件或原始证据改写。

### 2026-10-21：撤下RGB独立曲线训练，新增QAQ暂定预测网格

按用户要求，移除Web的RGB独立曲线新训练选项；API/CLI也拒绝该模式，旧任务仅保留读取渲染以免改写历史。新增QAQ预测模型选项：原生颜色链输出直接按保存上游008a12f2的BT601 limited暂定坐标查5×9×9网格，8点三线性插值，系数/256后按行向量右乘显式3×3 response，加回输入并clip。无后置明暗／染色曲线、无灰阶保护门控、无大网格压缩；现有曲线＋网格方案仍可选。上游也要求外部提供response，默认单位矩阵只是未标定假设，Web提供JSON编辑和可逆／条件数校验，不能称为已恢复机内真实响应。

QAQ训练以稀疏Kronecker联合三平面受限最小二乘求解实际A*C*response的RGB残差，保持405×3个7位整数，邻居平滑.01；量化坐标微调也按response正确影响RGB三通道。前向预测／规格对齐上游，不宣称优化器逐行复制上游。模式接入原生与PC交替、多起点、动态权重及感知评分；最终重建使用任务绑定的响应矩阵。新pipeline校验响应一致性，RAW预览自动复用同一渲染；BIN和验证ARW仍只含原生参数。

36项回归通过，含运行保存的上游源码并逐点比较predict、pack字节一致、非单位response训练及量化目标下降、灰阶门控恒1、退休RGB训练拒绝与旧渲染兼容、API传参。非单位response小规模整体训练导出与validation/gray指标复现通过，test RGB RMSE5.6413、显示平均DE00 2.2812，仅流程证据不作精度优于旧方案结论。证据research/r5_custom_lut/evidence/web_qaq_grid_20261021。无相机、Edit采集、固件或历史数据改写。

## 八、参考项目与致谢

感谢以下项目公开研究方法和工具。本项目的R5地址、结构适配与实机验收由本工作区单独核对；引用上游不表示上游作者验证或支持R5版本。

| 项目 | 本研究使用范围 |
|---|---|
| [Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/086df3b1e33dfa0206553ac2bb003535c58ddb80) | 当前FL2／FL3方法的直接依据，固定提交`086df3b1e33dfa0206553ac2bb003535c58ddb80`。参考AP／CP补丁、六槽个人设置、CC1／block13、Gamma以及SD与线刷分离的流程。R5不照搬M4分区号。 |
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE/tree/2328d18ce640e6c8cd9341efcf0043ce9042a135) | BootROM串行引导、RP2040桥接、fastboot与eMMC加解密的研究依据。该参考树未发现明确许可证，公开仓库不捆绑其源码、UF2或RAM载荷；历史本地构建身份另行核对。 |
| [DavidBuchanan314/fwtool.py，a7iv分支](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv)及[ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | Sony固件容器、文件系统、FDAT解包与格式研究基础。相关工具按其原许可取得。 |
| [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload/tree/1619f938663a36d41e72302a8cfee89a0f6acd1a) | 备用服务模式路线的资料研究；未用于本次R5部署，不作为已验证刷写步骤。原文为CC BY-SA 4.0，本文不转载其技术文档。 |
| [Capstone](https://github.com/capstone-engine/capstone)、[Unicorn](https://github.com/unicorn-engine/unicorn)、[Ghidra](https://github.com/NationalSecurityAgency/ghidra) | 指令审查、局部CPU回放与反编译分析。工具结果不能替代机身运行验收。 |

另感谢本地IED／RAW创意外观解锁项目提供十字段对照与Edit实验资料；当前没有核实其公开GitHub地址，因此不编造外部链接。Sony Imaging Edge Desktop为Sony官方软件，不属于本项目开源源码。

本研究公开的是主机脚本、补丁配方与研究说明；Sony原始或修改固件、供体完整色彩数据、机身备份、个人设置、签名私钥及第三方载荷不随源码发布。各工具保留原有许可证，致谢不替代再分发许可。
- [初始校验环境修改](../build_r5_partition1_verifykey_skip_20261014/README.md)。
- 图像视觉反馈来源为用户2026-10-17消息；后续430／431／432配对量化及430两张ST导出量化已分别记录于第五、六部分。ST玩偶脸部黄红减弱但明度略降，与最初“更明亮”的主观描述分开报告。
### 2026-10-21：R5原厂网格存在性核查与总效果单网格压缩

最新只读证据确认：R5原厂CP已有405点校正表及构建/排列/上传路径。原厂与4.18相应五个窗口逐字节相同；本轮REA上传器分析确认0x654字节复制和bank上传调用。历史两机各60组原厂指令受控重放仍保留，本轮Unicorn复跑退出132未获得新结果。不能把原厂代码存在等同于真实自定义激活、ISP坐标/response已标定或Edit支持。详见analysis/r5_native_grid_check_20261021/README.md。4.18导入文件仍未接入该网格。

按用户要求，Web整体训练结果中新增总效果压缩：冻结原有明暗曲线、灰阶染色和颜色网格完整输出，使用train及33³合成教师查询，整体压缩进一个5×9×9、每节点三项7位系数的网格；新预测函数只有输入坐标查表、乘显式response、加回输入和裁剪，不再使用原曲线/灰阶保护。三组平滑候选量化后按实际8位RGB＋DE00微调选择，valid/test不参与训练或选择。默认response为单位矩阵、坐标暂定，导出1215字节payload和完整报告/教师快照仅作离线验证，不改原PC参数、BIN、ARW或固件。

固定任务971cfa616f144ce192039d97aa96a7af的对LUT RMSE（实际8位）：原组合→单网格test5.6058→5.7487，valid5.8299→5.9743，灰阶训练0.4579→2.4598，24色2.5413→3.3250。独立test压缩损失2.1594，4096额外独立合成探针1.6796，系数触边0.0823%。此次尝试保留多数总效果但灰阶退化，不能称无损。Web显示三种误差和完整灰阶；39项回归及实际网页POST、ZIP下载与payload一致性核对通过，窄屏布局修正。全部新证据research/r5_custom_lut/evidence/web_total_grid_20261021/；无相机操作。



### 2026-10-22：独立压缩训练与全页面/RAW算法切换

按用户要求，将“压缩训练”按钮移至“开始拟合”旁。导入新LUT时，服务端任务连续完成原生拟合、tone-tint完整PC补偿、总效果单网格训练；无新LUT时，异步训练当前已完成PC任务。提供queued/running/done/error持久状态、错误回执和重启中断处理。保留旧压缩API与历史数据，训练报告与下载变为结果附属展示，任务ZIP也包含压缩网格、报告及教师。

结果对比新增“压缩前·完整PC补偿 / 压缩后·单一网格”，保留仅原生选项。测试色块、完整灰阶、正色、CC24、三项误差、亮度分区/感知色差和直方图由同一所选函数重算；压缩后不显示压缩前曲线为运行阶段。配方/LUT/pairs/教师散列绑定与压缩key校验，诊断缓存区分算法，异步响应防串任务。RAW首次解码保留原生颜色输入及LUT目标采样，切换算法复用同一采样而不重复解码或上传；记录算法、grid key与参数散列，旧图不冒充新算法。同RAW匹配限定source SHA；历史无缓存图需重新上传一次。Edit实际导出第三栏保持。

43项回归通过，新增来源变化拒绝、全部诊断算法一致、RAW缓存切换逐像素验证与训练状态成功/失败覆盖。实际HTTP新LUT任务c9d26a0228694077858927fa255500a8以小评估预算完成整条流水线，强制使用tone-tint教师并输出单网格；不作精度验收。网页实际独立训练完成，并切换示例971任务压缩前/后RMSE5.61/5.75。DSC00430真实RAW渲染及HTTP缓存复用均完成：两侧模型PNG逐像素等于各自函数，LUT图像像素不变，同source SHA；没有Edit采集或相机操作。证据research/r5_custom_lut/evidence/web_compression_workflow_20261022/。


### 2026-10-22：4.19 原生 5×9×9 网格配置与运行时接入候选

应用户要求停止 YGamma / AreaComp 查找。以4.18源码副本增加v3配置，每外观405×3个有符号7位系数及启用开关；兼容旧v2并在旧项覆盖时清除网格。AP解码、持久保存、容量握手和AP→CP传输同步扩容；CP普通外观路径替换表指针，复用原厂建表/上传器，无新增逐像素运算。沿用启动导入，无拍摄中热更新。PC response和明暗/染色曲线不导入固件。

4095种覆盖集合C codec/状态机、保存/重载故障测试、108条真实指令参数传输、104条容量握手、48种网格实际建表上传及8类回退、CC1/block13/BW/SE/loader/Gamma回放通过。AP只读e2fsck通过。Web44项测试及浏览器v3下载逐字节核验通过。4.19 DAT验签和全包独立解密通过，SHA256 305f319eca8105b354c357a325d809f41fb9eaa87276b5efeac03843de5ddbd8。详细格式、来源、源码、报告见analysis/r5_native_grid419_20261022/README.md。

本轮没有相机操作。4.19为未实机验收候选；真实ISP坐标/response、前置控制条件、上传触发和实际颜色仍未验收。当前实机已确认版本保持4.18，不以离线或PC图替代机内验收。


### 2026-10-22：4.20 SD 完整替换与网格诊断候选

见 [新增实现与证据](r5_native_grid420_20261022/README.md)。有效 SD BIN 全量替换，未列外观清除自定义覆盖，零字节/有效空 v3 清空全部，无文件或损坏保留旧配置；增加 R5IMPORT.LOG 和原厂网格选择/建表/上传返回诊断。152 场景、组件回归及4.20 DAT封装验签/全包独立解密通过，尚无实机验收。DAT SHA256 c6483a0a3f421251e08cb742b7dd5bfd7f2a5e65d3497dbcf8dec1b8255448be。当前已确认机身版本仍为4.18，无相机操作。

## 2026-10-23新增：独立探针采集与网格响应反推工具

`R5GridCalibrator/`现为独立Web，默认本机4190，不修改固件或原色彩工作台。上传BIN v4并选一项，生成一份包含12配置的新BIN，非网格颜色参数相同：ZERO、三通道正负、三坐标渐变、原表及交叉波形。原表和波形只作留出测试。探针包完整替换配置集，用户需保留源BIN以恢复；已支持v4的固件无需反复刷固件。

下面按批次上传ZERO与各探针JPG，可补重复ZERO检查漂移。工具保存BIN身份、配置/照片对应和样本来源，拟合暂定坐标通道矩阵/颜色交互与可选有界仿射坐标调整，训练/验证/测试严格分离，报告三类误差、原暂定/零修正对照、激励秩和坐标覆盖。输出为PC响应模型和预测代码，不是颜色BIN或新固件，尚未自动接入R5ColorLab。拟合只能约束已拍条件和探针覆盖，不唯一证明ISP内部算法；自然图像错位、曝光/WB/光线漂移及空间处理仍会混入差异。

6项合成/HTTP回归与JS语法通过，包含保参、已知响应恢复、测试投毒隔离、低秩/无效果、16位TIFF和完整上传导出流程。无真实R5标定样本，不能声称R5颜色已校准。见`analysis/r5_grid_calibrator_20261023/verification.json`及工具README。本次独立开发未自动发布GitHub。


### 2026-10-24：接入用户R5实拍网格响应

按用户要求以R5-grid-response.zip的refined-smooth模型替换新任务实测选项中的C2代理；原始JSON固定SHA256 6852ead83bf381215a8d721d1557cc73803f6ef60a0745971e8783144863c96b。11对探针，三通道秩3，留出RMSE1.9158、原暂定15.2171、零修正9.2282；颜色覆盖14/256单元，无重复ZERO漂移回执。没有C2直接对比，不宣称全色域/跨外观ISO/WB验证。原C2模型及数据保留供旧配方，不覆盖历史任务；旧压缩实现散列门控保留，必要时重压缩。

R5ColorLab和research工作台同步paired_response：本次仿射坐标、三线性系数/256、RGB相关通道响应，零表恒等；直接拟合、压缩、整数选优及照片预测统一get接口。新响应不走TPS照片加速器。与反推工具逐点/零表/照片render一致，合成已知表求解误差0，旧C2加载仍通过，验证脚本analysis/r5_measured_response_20261024/verify.py。未改固件/设备，未自动发布GitHub。

2026-10-24补充：已按用户要求使用IED项目v2.2转换链生成GFX100S II合成RAF色卡，见`exports/GFX100SII_chart_20261024/`。完整目标RAW阵列与3700点训练数值独立验证通过；合成预览替换历史照片预览。仅固定合成源的tile填充截取有本地适配，IED源未改。RAF是容器转换的合成色卡，不代表富士传感器实拍；Adobe/LibRaw裁切分别顶移1/2行，LibRaw建议6335行输出尚未加入Web目标导入适配。实际显影软件打开仍待用户验证。


### 2026-10-27：4.30启动切换等待与同次开机SD更新

用户报告当前自定义滤镜开机数秒可预览，但几十秒不能切换；SD新BIN需两次重启。源码确认恢复后同一worker还阻塞于SD发现和最多30秒、期待全部配置mask的网格诊断；新配置存盘后，CP传输/初始E4失败缺少完整同次恢复。未取得本次机身日志，不定为唯一实机原因。

新目录analysis/r5_custom_menu430_startup_20261027仅改四个生产文件：thread、session、grid log、filter runtime。无fd等待点服务选择；诊断只期待当前配置；双槽独立就绪选择、30秒发现与15秒读文件独立预算；完整内容相同跳过写入及重复上传；有效清空/无效保持/原子保存不变。完整bank最多三次同次重试，自动选择一秒退避最多30次，主动选择绕过退避。恢复启动先复用旧drive后，迟到的当前epoch READY会触发同次开机重读，重复通知不重复提交。4.29菜单源码及CP423/422生命周期精确保持，未增加新线程或修改ACK/父值退出标准。

AP 81fa2ea3ee89d30715d7ab69f9eca92da837139a0ab1a32bed1f3799067d7c6e，RX62776/BSS136392。当前AP执行180项双PIE SD、worker15、诊断7；实际AP/CP30次选择和两路丢SEAL ACK复用已封口bank的同次恢复；原生菜单/名称/对象生命周期等回归通过。本版不沿用旧162项SD精确继承证明。20份必需回执、21项门控；最终DAT签名/CRC/篡改拒绝、AP/CP提取及751577088明文字节完整独立核对。交付research/r5_custom_lut/build_r5_4.30_startup_20261027/BODYDATA.DAT，754525608字节/BCD3004，SHA256 96bf66afa4cdfdb64756cfbd1d1f66f94ee6ee0d30550b4624fc3fb12cb651a7。

没有相机、SD、Web或远端操作，原镜像和历史交付保持。合成时钟不代表机身耗时；同步原厂Fsys仍可能超时，永久失败仍会阻止本次应用。实际冷启动/恢复/菜单及预览JPG待用户验收。


### 2026-10-28：4.31菜单移动应用、原生列表及错误分类

用户确认4.30加载快了，但上下移动必须确认才应用，左侧样式简陋，实际应用后仍显示应用失败；因此4.30菜单交互/样式/提示实机验收失败。原生路由回放确认进入同层D9时旧父presenter已销毁，旧代码仍持有last_parent并直接调用其update；此外worker成功后的父页核对失败被错误归为应用失败。未取得机身崩溃/阶段日志，未把全部实机异常定为同一个原因。

4.31上下移动/触摸立即完整应用并保存、保留页面；确认/返回等待精确请求完成并用原生资源解析器核对提交值，再交给原生pop重建父菜单；删除旧父对象缓存及解引用，已完成同项不重复请求。左侧恢复原生列表高亮和选中，右侧仅全称，无更新/调整入口。显示资源核对独立分类，真正ACK/E4/保存失败仍失败。4.30四个worker/启动生产源码精确保持，CP423与422参数/网格生命周期保持。

AP 3c832336b73fc5d8b5a902faebd07249821888a17d3609831def42d4419ba941，RX63400/BSS136384。当前AP交互/原生控件/生命周期、180项SD、15项worker、7项诊断、跨核30选择及两路丢SEAL ACK恢复通过；23份必需回执、26项门控；DAT独立签名/CRC/篡改拒绝/AP与CP提取及751577088明文字节逐字核对通过。交付research/r5_custom_lut/build_r5_4.31_interaction_20261027/BODYDATA.DAT，754525608字节/BCD3104，SHA256 8944fef8d8a00e9d45a919851fa98c53d3e0db916ef4f0cf45ede643993cd2f0。

本轮仅本地开发与离线封装，无相机、SD实物、Web/GitHub操作。物理字体/遮挡/透明度/触摸、原厂事件时序、冷启动及拍摄仍待实机；没有用离线模拟替代用户验收。


### 2026-10-28：4.32控制轮与自定义滤镜菜单同步

用户确认4.31上下按键已正常，但旋转控制轮仅切换滤镜、界面不动。因此4.31控制轮同步未通过实机验收，不能以其离线按键/触摸测试宣称覆盖旋转事件。

4.32让控制轮与上下按键共用自定义选择通路，联动焦点、全称、原生列表和应用保存，连续滚动按每个事件一步选择，首尾边界不越界，不读取消息内的步数或方向；不进入原厂Look设置器。生产源码仅页面相对4.31变化；4.31原生列表与父级重建/错误分类，4.30四个启动worker源码，以及CP423/422参数和网格生命周期精确保持。

AP a68bdc37ad95c1254e0d70bbab9531f686ed9436fbb303fe5541dcaa6ee1d89a，RX63464/BSS136384。当前AP控制轮/交互/原生控件/生命周期、180项SD、15项worker、7项诊断、跨核30选择及两路丢SEAL ACK恢复通过；24份必需回执、30项门控；DAT独立签名/CRC/篡改拒绝/AP与CP提取及751577088明文字节逐字核对通过。交付research/r5_custom_lut/build_r5_4.32_wheel_20261028/BODYDATA.DAT，754525608字节/BCD3204，SHA256 f75f4a6efa286e3a6af0ed60cda6b92824d5ab18a8866cd167b9d2ec2b910e8b。

本轮仅本地开发及离线封装，无相机、SD实物、Web/GitHub操作。真实控制轮速度与GUI事件队列、字体/透明度/触摸、冷启动和拍摄仍待机身验收；未用合成时钟推定相机耗时。


### 2026-10-28 发布范围与历史产物清理补充

4.32已公开源码、构建和打包脚本，按用户明确更正不上传固件DAT本体。main/tag为0efd809d95a827912e50d872ba522faa7e869a1c；同步最新直接目标网格算法、R5实拍v2、100MP unity-WB合成RAF、12款模拟配置和两套工作台。v4.24/v4.28 Release及标签已撤下；历史源码记录保留。发布与清理回执见analysis/github432_publication_20261028/。

本地清理25个旧升级DAT及非当前依赖的生成镜像，实际释放约7.21GiB；566个当前保留输入核对一致。4.32冷启动、真实滚轮/LCD及拍摄仍未由发布操作证明，沿用前述验收边界。用户要求停止新增验证后仅完成上传及清理，临时训练目录/日志已删除；原始机身备份与严格4.03/4.04未改。

### 2026-10-28：从R6 ST RAW逆算参数并比较R5原厂

按用户要求，将本文第三／四节的已知正向关系用于逆算。直接只读解析`/Users/LOCAL_USER/Documents/DG707670.ARW`，型号ILCE-7RM6、软件v1.01，SHA256为`3167b87fba9301b3dec6822c6c7cd3898b42df2ef6563bc4229989d9f39b3a52`。R5机内参考为原厂4.00 BK4与CP；短字段及完整114字段另与保存的DSC00430.ARW比较，未将保存RAW的拍摄／编辑来源视为已认证。

| 项目 | 实际逆算范围 | 与R5原厂／保存RAW的比较 |
|---|---|---|
| CC1 | B、A1−B、A2−B，共24个int16；48字节 | 差分存储值16／24不同；还原绝对三端点后15／24不同，最大绝对差91 |
| block13 | A1全部16槽×6项；192字节 | 94／96不同，最大绝对差252；7800独立矩阵与首槽展开精确相同 |
| Gamma | 7806÷2，前128个u32；512字节 | 与R5和FX2原厂ST照片slot6的128点全部相同 |
| Knee point／slope | 正常范围代表值2048／928 | 与R5保存RAW有效值相同 |
| 有效YGain | `[540,488,468,444,424,404,380,360,336,316]` | 与R5保存RAW相同；ST首项覆盖不等于静态默认表首项512 |
| 780F公共打包值 | 坐标、间隔换算、基准、控制位及字节 | 与R5相同；头24／尾60字节用解出的值重新打包精确相等 |

新逆算函数另用R5、FX2已知ST样本验证：CC1全部24项、block13 A1全部96项、Gamma前128点均精确恢复各自原厂BK4／CP字节。R6全部114标签与历史独立解析报告逐字节相同；所有可逆算输出均正向回算通过，全部输入读前／读后散列保持。两份ST记录114字段中90项相同、24项不同，其中19项差异在各自样片的所有外观内共用，包含白平衡RGGB输出及尚未建立机内对应的私有字段，不能直接解释为ST调色差异。

恢复边界：R6的CC1是转换成已验证R5差分表示，尚无R6原厂BK4认证其原机布局。block13的B、A2与bank尾192字节未编码在这些RAW标签中；公共打包值也不能唯一恢复完整原始头部。Gamma缺第129点、其他内部曲线和附属记录；R5／FX2的第129点均为130946，不能据此声称R6该点已经恢复。Knee／YGain原输出有uint16回绕，只确定正常范围代表值及对应模数，不能逆推出指针地址或默认／覆盖分支。没有生成完整bank、可导入BIN或固件，也没有相机操作。

完整逐项表见[本次比较](r6_st_reverse_20261028/comparison.md)，全部恢复值、114字段原值与来源散列见[comparison.json](r6_st_reverse_20261028/comparison.json)；[逆算脚本](r6_st_reverse_20261028/reverse_and_compare.py)及48／192／512字节研究片段在同目录，Gamma逐点表为[gamma128_comparison.csv](r6_st_reverse_20261028/gamma128_comparison.csv)。本结论限于ST照片保存参数，不代表跨机最终JPG一致或R5实际功能验收。


### 2026-10-28：4.33升级参数保留、R6 ST、Fn注册及AWB

按用户四项需求，以冻结4.32为功能基线生成4.33／BCD3304。参考指定Erlla文档并锁定最新d4649e21f72e9074031c0c95c9ec2dc23ecb6807，其文档与已保存20261019版本一致；采用完整generic模板+backup.sum方法，保留原086df3b的动态B/A1/A2，不引入fixed-a1或运行时强制写回。

已确认4.32所继承strict4.04 TAR中的12份地区模板颜色仍为原厂默认，原厂attrs8迁移会从新模板取CC1/block13/AWB，导致仅在个人设置里部署的颜色被覆盖。4.33补全12份模板每份10处FL23、2处R6 ST和1处AWB，共13个参数范围/2746字节范围，另维护BK4校验。每份实际1976字节变化，FL23完整四个768字节bank均等于既有动态供体；backup.sum仅12项CRC更新，MainDest和目录行保持。两份原始迁移核72案例与4项异常拒绝、独立模板字节复核通过；LOOK保留证明对应所验证mode5，不将政策核心回放冒充整机升级。

ST照片bank0更换CC1全部24项和block13 A1全部96项，其他bank/映射保持；bank0原厂别名仍按原映射共用新数据。B/A2、尾部、视频和完整Gamma保持R5，可见Gamma128点及Knee/YGain相同。AWB模板930/931为70/FF（白色112、氛围-1），932/933为00/06保持。当前CP原生CC1 63例、矩阵320例和AWB336例验证新值进入消费，标准AWB112例保持；CC1调整子服务输入为声明fixture，完整矩阵/AWB无helper桩。

Fn在原生颜色/色调候选组追加MID635，复用原厂Creative Look的still/movie标志，play不启用；仅增加手动可注册项，不自动占用或替换Fn槽位，保留原有选项、保存和调用通路。普通菜单与Fn共用Creative Look图标021C6410，名称仍为自定义滤镜。AP 65bd99095f626f990890156c0e536d56394c75313452caa451322e1148c1faec，候选表41字节差异；生产源码仅menu描述符初始化+c/+60两处图标常数变化，其余22份编译对象逐字等于4.32。重链接会更新相关地址，RX63464/BSS136384预留不增。CP 8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d精确继承423，原422参数/网格生命周期保持。Fn专项验证及完整菜单/轮盘/生命周期、180项SD、worker15、grid7、跨核30次选择和丢SEAL ACK恢复全部绑定最终AP。原生注册handler和24槽两种目标/两PIE共96例影子保存恢复通过；物理BKID/eMMC提交和冷启动持久性不由影子回放代替。

交付research/r5_custom_lut/build_r5_4.33_color_fn_20261028/BODYDATA.DAT，754525608字节，SHA256 ca8f91170e8b92aeab0e037622350f517331426b98e0a22f2232af2828254032。独立验签/CRC/篡改拒绝、AP/CP提取、16个TAR替换成员及751577088明文字节完整核对通过。来源与门控、Fn及原生消费/迁移回执见analysis/r5_firmware433_20261028。无个人设置镜像、相机/SD实物/fastboot或远端发布操作；实际升级、Fn/LCD/事件时序、冷启动及预览/JPG仍待实机，离线不代替功能验收。


### 2026-10-28：4.32／4.33 ST与AWB八组实拍RAW核对

只读桌面“白平衡对比”DSC00568–DSC00575的8 JPG／8 ARW，按用户顺序区分旧／新ST、PT、5300K／自动。全部1/80秒、f/4、ISO320、AB／GM为0；前四张软件4.32、后四张4.33，四张自动均White优先。SubIFD、SR2、LibRaw实际RGGB交叉一致；旧ST／PT自动均2599/1024/1024/1714，新ST2566/1024/1024/1720，新PT2399/1024/1024/1787。ST红增益−1.270%／蓝+0.350%，PT红−7.695%／蓝+4.259%；自动没有可信最终Kelvin字段。本组无氛围优先样本。

新ST的48字节CC1和192字节block13 A1在全部四份4.33 RAW中精确等于R6反算片段与冻结4.33交付目标散列；旧ST精确等于R5原厂。差分存储16/24、绝对端点15/24、A1 94/96项变化，独立7800矩阵核对通过。PT三项及ST可见Gamma128点八张全部保持，未知第129点不扩大结论。固定5300K对照支持新ST木板红味减轻、粉红毛绒彩度收敛；小范围纹理／位移和照明漂移限制精确归因，不作肤色准确率结论。

Bayer只解包扣黑、不施加WB／矩阵／Gamma，固定墙面ROI检查：574→575红绿比仅变0.026%–0.039%、蓝绿比0.141%–0.198%，相较AWB增益变化很小。575 JPG墙面a*、b*均下降，呈青冷方向，若物体应中性则不支持白色中性改善。573手动照片后台Auto等于574实际应用，约19.304秒后的575才明显变化；尚无法排除收敛、场景分支或外置传感器输入，不能断言PT导致AWB变化，不能把全部幅度归因88→112。没有当前参数分区／RAM回读，RAW也不直接保存930配置字节。112是否过强待固定PT的重复收敛序列复核，尚未改动固件。

证据analysis/r5_st_awb_photo_comparison_20261028：raw_readings.json、raw_color_tables.json、patch_metrics.json、verification.json及README；八图对照comparison_compact.jpg、ROI位置patch_locations.jpg。16原片读前／读后散列保持，新增脚本和产物散列落盘。仅追加照片分析证据，未操作相机／SD／固件／保护备份或远端项目；Fn、FL23升级保留、冷启动和全场景成像不由该组照片验收。


### 2026-10-28：4.34动态图标资源修复及白色优先97

用户报告4.33自定义滤镜图标无法加载，要求与原厂Creative Look动态状态一致，并将白色优先112改97。已确认0x021C6410为string_english_f.uxc中的Creative Look帮助文字，descriptor+0x0C和getter1BD5630属于帮助通路；4.33将其写到图片fallback+0x60是资源类别错误。旧回放只检查资源ID送入sprite，不能证明图片存在，不能沿用其图标通过结论。

4.34保留合法帮助字段+C，将+60恢复sentinel，新增20字节A64 wrapper，仅在原厂图片取图入口1BD63B4把MID635转为MID1E6，重放原cmp w1,#CA4后回1BD63B8。原厂PID690当前状态getter28AE4B0／BSS7F207E8决定所选行，真实动态链1BD642C→1BC50EC取原厂当前图标；type保持原生6，不改私有选择／路由／标题。原厂12状态与候选动态图标、真实UXC图片记录和解码分别核对。用户最新要求不再追查主菜单左侧小logo，本版不据此认定其类型或含义。

AP c61d151fd7da84896d675dd7be26a8319156598206556e6e5d50ea2da11406b3，24个编译对象中新增1个icon ASM、原menu初始化移除错误fallback，其余22个与4.33逐字相同。RX63480／BSS136384；原生前缀反向恢复精确，Fn候选表仍41字节变化，CP 8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d精确保持423。原厂12状态的Fn图片resource／type与候选同状态对照，注册／激活／返回及现有25项菜单／控制轮／生命周期／SD／跨核回归全部绑定当前AP。

AWB property02A40000+930白色97／+931氛围−1，连续61ff0006，局部系数自动450；12地区模板与4.33逐字节仅白色112→97和BK4校验差异，backup.sum仅12CRC。CC1／block13整属性、R6 ST／FL23及Gamma保持。原生迁移72例、异常拒绝4例、CC1 63例、矩阵320例、AWB336例通过，标准AWB112例保持。该系数是后段修正参数，不直接表述为可见光／红外硬件权重。

交付research/r5_custom_lut/build_r5_4.34_icon_awb_20261028/BODYDATA.DAT，754525608字节／BCD3404，SHA256 1aeccd8f7fd6c1672b8fcd60ee1389c9b85a40a8aef51d6a720d898ecf9a1da9。独立签名／CRC／篡改拒绝、AP／CP提取、16个TAR替换成员、12地区模板及全部751577088明文字节核对通过。详见analysis/r5_firmware434_20261028/release_tests/delivery_verified.json。未操作相机、SD、fastboot或远端；实机LCD图标与刷新、升级／冷启动、AWB收敛与成像仍待分别验收。


### 2026-10-28：FUJ新版12滤镜连续性训练全部完成

正式批次dbd6a094691141ed8eb66a6d40fe58fc于北京时间20:58:59完成，12任务全部done，输出连续性30／参数平滑30、高精度2000评估／12起点，最终网格直接拟合目标，压缩后交替和灰阶微调关闭。合并R5NATIVE.BIN 29552字节，SHA256 e3375e9f5fb8e32ae4dce5edab42c6024f1bc7d969abf7c2e01ded2b53419bc2，位于research/r5_custom_lut/web/batches/dbd6a094691141ed8eb66a6d40fe58fc/。本次只读核对12项名称／设置／网格、导出审计及配置重新编译逐字一致（按现有导出策略移除仅Web使用的export_sources）。上一正式合包a67c9e7d…保持。见analysis/fuj_continuity_formal_20261028/completion-verification.json。未重新训练或操作相机；该批完整照片／机内成像尚未验收。
