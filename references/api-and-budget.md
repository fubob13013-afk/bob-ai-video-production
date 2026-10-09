# API执行与预算

署名：Bob。文档链接是发现入口；每次项目接入时读取最新版本。

## 官方文档

- Seedance 创建任务：https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh
- 查询任务：https://docs.volcengine.com/docs/ark/get-video-generation-task-api?lang=zh
- 查询列表：https://docs.volcengine.com/docs/ark/list-video-generation-tasks-api?lang=zh
- 火山方舟价格：https://docs.volcengine.com/docs/ark/model-pricing?lang=zh
- MiniMax 同步语音：https://platform.minimax.cn/docs/api-reference/speech-t2a-http
- 可用音色查询：https://platform.minimax.cn/docs/api-reference/voice-management-get
- 系统音色：https://platform.minimax.cn/docs/faq/system-voice-id
- 计费：https://platform.minimax.cn/docs/guides/pricing-paygo
- 错误码：https://platform.minimax.cn/docs/api-reference/errorcode

API Key 与网页会员通常是独立授权/计费体系；依据当前官方文档和用户账户核实，不凭网页可生成就假定 API 可用。需要发票时查实际平台账单与开票规则，不把预算估算当发票金额。

## 配置与密钥

工具从指定环境变量或用户授权的密钥文件读取。不要在命令里粘贴真实密钥，也不输出文件全文。推荐环境变量 `ARK_API_KEY` / `MINIMAX_API_KEY`；明文密钥文件只放项目外或受保护位置，分享时排除。

先预览请求 JSON。工具不会替你验证模型是否开通、图片尺寸、参数兼容或价格；执行者负责先验证。图片可使用官方允许的公网 URL 或 data URL。本地照片通过 image_url 的 data URL 传输也等于上传给服务商，必须符合项目授权。

## 预算与提交

累计预算包含小样、失败/不确定请求、返工和其他服务。先估算，再为每笔生成设置预留额。返回 usage 后按确认的当前单价更新；优惠仅在账户已确认时计入。若同一项目存在另一个工具的账本，`--initial-spent` 必须包含这些费用。

案例历史估算：720p24fps视频 tokens≈秒数×宽×高×24÷1024；当时图片参考 Mini 的刊例单价23元/百万tokens。MiniMax HD当时3.5元/万字符，一个汉字按2字符计。**仅为项目案例，不是当前价格保证。**有视频输入、不同模型/分辨率/账户套餐时规则会改变。

脚本示例（`python` 换成当地可用运行时）：

```text
python scripts/api_runner.py preview --request 项目/请求.json
python scripts/api_runner.py init --ledger 项目/费用.json --budget 80 --initial-spent 27.81
python scripts/api_runner.py submit --request 项目/请求.json --provider ark --key-env ARK_API_KEY --ledger 项目/费用.json --name 11-01-v1 --reserve 4
python scripts/api_runner.py poll --provider ark --key-env ARK_API_KEY --ledger 项目/费用.json --name 11-01-v1
python scripts/api_runner.py submit --request 项目/语音.json --provider minimax --key-env MINIMAX_API_KEY --ledger 项目/费用.json --name 11-01-voice-v1 --reserve 0.05 --output 项目/配音/11-01.mp3
```

`init` 不覆盖账本。已花费用和未结算预留额都计入预算；脚本没有平台扣费硬限额。默认不会自动释放预留。核对用量/账单后，可用 `settle --cost 金额` 替换该笔预留，不能仅因任务失败就填0。

## 不重复扣费的关键

创建任务前落盘预留记录；明确记录业务错误、网络不确定、任务ID和输出。**POST超时或本地记录失败，不自动重复POST。**GET状态查询可在网络恢复后重试。

无ID的未知任务先查官方列表、提交时间和输入信息；无法唯一识别时请用户协助，不凭“列表里最近一个”强行归属。只有确认服务端没有创建任务，才更换版本重新提交。

Windows可能短暂锁住被频繁写入的JSON：保留唯一命名日志，对本地索引写入短暂重试；这不授权重试付费请求。工具账本带单进程锁，遇到残留锁先确认无运行进程和未处理日志。

## 返回处理与下载

Seedance异步：POST拿ID→GET查询→成功后保存usage、下载临时video_url到临时文件→完整检查→更新完成状态。下载媒体URL不发送API密钥；链接可能过期，应及时按用户授权保存。

MiniMax非流式：检查 `base_resp.status_code`，再解码 `data.audio` hex。先保存音频，之后写日志；不要只判断HTTP200。案例错误1008为余额不足、2013为参数错误；按当前错误文档核实。MP3可用比特率以文档为准，192000并非所有接口都接受。

脚本只保存经过授权请求的音频；不会自动查价、替用户充值、申请发票、克隆声音或批量无限重试。
