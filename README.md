# 汀线 · 海滩无障碍铺毯换段

汀线把现场滚轮通行测验、潮窗内的换段校核和接班登记连在一起，为汀州海水浴场的 12 人值班组提供海滩铺毯地图。

值班员原先在群聊报湿度、在纸计划圈出潮水接近的毯段、在下个班现场交接。三项经常漏交的是轮辙测验、救援旁线和换段前后状态。操作员在这里登记砂面测量与现场判读，班长审核新旧毯段能否维持两条通路，接班员拿到签过的换段令并复核当前铺毯。数据为虚构培训班次，实际换段由现场值班组决定。

## 启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose exec -T backend python -m scripts.seed_demo
```

- 值班工作台位于 [localhost:18341](http://localhost:18341)。
- API 文档位于 [localhost:19341/docs](http://localhost:19341/docs)。
- 本机 MySQL 端口为 `17841`。
- `docker compose logs -f backend worker` 可追踪业务接口及预测任务。
- 本地修改后可用 `docker compose up -d --build backend worker frontend` 重建应用镜像。运行 `docker compose down -v` 会删除此项目的演示库与队列。

| 角色 | 邮箱 | 可执行操作 |
|---|---|---|
| 查看 | viewer@demo.test | 查看分段、测验、换段令和交接记录 |
| 操作 | operator@demo.test | 登记测量、运行预测、填写结果、草拟换段、登记交班 |
| 班长 | admin@demo.test | 操作席全部功能与签发换段 |

演示账号密码均为 `Demo2026!`。修改 `.env` 的 `JWT_SECRET` 及数据库密码后再用于独立环境。

## 早班演练

1. 07:20 打开分段示意，核对北坡 A1、接驳 B2、回转 C3 和救援旁线 R1 连通。
2. 07:35 记录备用 D4 的坡度 2.5%、湿度 22.3%、轮辙 3.0 mm。种子库含同一早班测量 `TR-D4-DAWN`。
3. 07:40 登记一条新测验并点「用模型推演」，待 Redis worker 写回可通行概率。
4. 07:45 在现场滚轮通过后登记「现场可通行」，同时将本次判读纳入下次推演参考样本。
5. 08:05 尝试用 D4 替换 C3，草拟潮窗 10:10–10:35。推演标出浪线观察台不可达，班长签发时收到拒绝。
6. 08:10 将方案改为 B2 → D4，沿用 D4 的测验，班长核对两条通路后签发。
7. 10:10 换段图显示 D4 已铺和 B2 备用，路线检查保留 A1 → D4 → C3 和 R1 → D4。
8. 10:35 在值班交接中选择签发的换段令，登记接班人「救生岗 周班长」并查看签发快照。

## 模型、规则与目录

测验用高斯朴素贝叶斯。对可通行、受阻分别拟合坡度、湿度和轮辙的均值及方差，并带入各类的样本先验，使用对数分数归一化求可通行概率。每类至少 4 条现场判读。方差按测量精度设置下限，阈值为 0.8。在相同判读集合和输入下计算可复现。未判读的新测验作为留出输入，预测和现场结果分别存储。签发还要求两者都判为可通行，且广度优先搜索确认救援和公众通路依旧连通。

### 模型盲测批次

班长在「模型盲测」页挑选**尚无预测和判读**的滚轮测验开测，协议保证评估独立于训练：

1. **开测锁定训练样本**：开测瞬间把全部已公开判读冻结成快照（`blind_batches.locked_snapshot`）并记录样本数。参测毯段以往判读若已在库，密封期同样不参与拟合。
2. **密封提交**：预测走 `sandmat-blind-classify` 队列，仅按开测快照计算，结果写入 `blind_sample_count`；现场判读可先交、也可在推演时一并密封。密封期详情接口只回进度（`has_prediction` / `has_observation`），不回具体判别。
3. **统一揭晓**：全组预测与现场判读齐备后由班长一次性揭晓，盲测结果只出一份；报告给出把**现场受阻判成可通行**的次数（`false_clear_count`，方向性差错）及判对条数。
4. **揭晓后才回流**：揭晓前日常推演（`trials.classify_job`）排除所有密封批次的判读；揭晓后这些样本才进入日常训练池。
5. **中断可恢复**：worker 重启后把处理中的任务移回队列，盲测任务对已出预测幂等返回，重试仍用同一份开测快照，不更换训练样本。

末条测验支持在同一次推演请求里同时提交现场判读与预测，整批仍只产生一份揭晓报告。

| 内容 | 路径 |
|---|---|
| Python / FastAPI 路由及 DB 事务 | `backend/domain.py` 和 `backend/infra/` |
| 分类、盲测批次、通路校核、换段业务与演示班次 | `backend/sandmat/`（盲测见 `blind.py`、`blind_states.py`） |
| MySQL 8 关联业务表与盲测迁移 | `backend/migrations/10_sandmat.sql`、`20_blind_batch.sql` |
| Redis 任务与心跳 | `backend/worker.py` 和 `backend/infra/queue.py` |
| 离线盲测业务测试（标准库 sqlite3，无需容器） | `backend/tests/`，`python3 tests/run_offline.py` |
| Nginx / 原生 HTML、CSS、ES 模块 | `frontend/` |
| 五个工作页（含「模型盲测」）与共享地图、状态标记 | `frontend/pages/` 和 `frontend/components/` |

业务枚举在 `backend/sandmat/states.py`、MySQL 约束及 `frontend/constants.js` 定义，供试验、地图和交接页使用。角色枚举位于 `backend/infra/roles.py` 和 `frontend/session.js`。环境变量见 `.env.example`，主要有 `COMPOSE_PROJECT_NAME`、三个端口、`DB_PASSWORD`、`JWT_SECRET` 与 `SEED_DEMO`。容器为 frontend、backend、worker、db、redis，共享产物卷由 Compose 管理。许可为 MIT，详见 `LICENSE`。
