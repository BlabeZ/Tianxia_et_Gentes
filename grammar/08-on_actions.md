# 08 on_actions（行动钩子）

> 来源：HOI4 官方 wiki `On_actions` 页（2026-08-16 抓取），CC BY-SA 3.0。

## 1. 基本结构

- 存储于 `common/on_actions/*.txt`；文件根块 `on_actions = { ... }`，每个钩子一个块。
- 每个 on_action 最多两个参数：
  - `effect = { ... }`：必填，触发时执行的效果块
  - `random_events = { ... }`：可选（仅默认作用域为国家时），按权重随机触发其中一个事件（`0 = 事件ID` 表示不触发）；事件 trigger 为假时不会触发
- 多个 random_events 块各自独立选一个。
- **ROOT 是默认作用域**（除非另有说明）；FROM/FROM.FROM 为附加作用域。
- **on_action 只在游戏开始后执行**——历史文件与 bookmark `effects = { ... }` 中的操作不会触发它们（如 set_politics）。

## 2. 文件示例

```pdx
on_actions = {
    on_startup = {
        effect = {
            every_country = {
                limit = { is_ai = no }
                country_event = welcome_event.1
            }
        }
    }
    on_state_control_changed = {
        random_events = {
            1 = germany_state_control.1
            1 = germany_state_control.2
            3 = 0
        }
        effect = { ... }
    }
}
```

## 3. 常用钩子速查（本项目相关加粗）

| 钩子 | 触发时机 | 作用域 |
| ---- | ---- | ---- |
| **on_startup** | 新游戏第一天（选国后）；**读档不触发** | 默认作用域 **none**（不会逐国执行！必须显式 every_country/标签作用域） |
| on_daily / on_daily_TAG | 每天（每国分别执行；性能重，慎用） | 国家 |
| on_weekly / on_monthly（+_TAG） | 每周/每月 | 国家 |
| **on_government_change** | 政府变更（含 set_politics 与 start_civil_war 双方；不含被傀儡）；**总会同时触发 on_ruling_party_change** | 国家 |
| **on_ruling_party_change** | 意识形态变更（含被傀儡、控制台换党）；`old_ideology_token` 为存旧意识形态的临时变量 | 国家 |
| on_new_term_election | 选举发生/被 hold_election 召唤 | 国家 |
| on_declare_war / on_war / on_peace / on_capitulation | 宣战/开战/停战/投降 | ROOT=宣战国/参战国/投降国，FROM=目标/胜利方 |
| on_annex / on_civil_war_end / on_puppet / on_liberate | 吞并/内战结束/和平会议傀儡/解放 | ROOT=胜利方，FROM=被吞并方 |
| on_state_control_changed | 州控制者变更 | ROOT=新控制者，FROM=旧控制者，FROM.FROM=州 ID |
| on_generate_wargoal | 生成战争目标 | ROOT=所有者，FROM=目标 |
| on_naval_invasion / on_paradrop | 两栖登陆/空降 | THIS=被登陆州，ROOT=入侵国，FROM=出发州 |

## 4. 本项目实践（T-049/T-046 对照）

- `on_startup` 默认作用域 none → 我们的钩子先 `every_country` 做状态校验（`TXG_validate_project_party_state`），再按 16 国标签显式分派好感网络（`TXG_opinion_network_<TAG>`）——符合 wiki 要求。
- `on_ruling_party_change` 中 ROOT=换党国家 → 我们按 `has_country_flag = <TAG>` 分派该国好感重算（KR 模式 remove 全部再 add）。
- 换党触发时 `old_ideology_token` 可读旧意识形态（后续可用）。
- on_government_change 总会同时触发 on_ruling_party_change——两钩子效果叠加时注意幂等。
