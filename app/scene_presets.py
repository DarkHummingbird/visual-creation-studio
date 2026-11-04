# Adapted from wzj177/ecommerce-image-suite scripts/generate.py
# Commit 2d508bd990df0397026406f210a5915b2c955469, Apache-2.0.
# Modification: extracted the pure scene description helper only.
def _scene_to_env(scene_zh: str, product_type: str = "") -> str:
    """将中文目标场景词映射为英文环境描述，用于 lifestyle / multi_scene prompt。
    product_type 用于在场景词模糊时推断类别默认环境（兜底）。"""
    s = scene_zh
    # ── 服装/通用生活场景 ──
    if any(k in s for k in ("居家", "睡", "卧室", "内衣", "睡衣", "室内", "家中", "闺蜜")):
        return "cozy bedroom interior, soft ambient lamp light, satin bedding, intimate home setting"
    if any(k in s for k in ("海边", "沙滩", "度假", "海滩", "海岛")):
        return "tropical beach, golden sand, turquoise ocean backdrop, sunlit coastal scene"
    if any(k in s for k in ("约会", "浪漫", "晚宴", "romantic", "date", "情侣")):
        return "intimate romantic restaurant terrace, warm candlelight, evening ambient glow"
    if any(k in s for k in ("运动", "健身", "瑜伽", "跑步", "gym", "sport")):
        return "modern fitness studio or park path, natural light, clean athletic atmosphere"
    if any(k in s for k in ("派对", "聚会", "party", "gathering", "社交")):
        return "chic social venue, warm ambient lighting, stylish gathering atmosphere"
    if any(k in s for k in ("办公", "通勤", "上班", "商务", "office", "work")):
        return "modern office or minimalist café workspace, clean professional atmosphere"
    if any(k in s for k in ("校园", "学校", "课堂", "campus", "school")):
        return "sunny campus green lawn or café, shallow depth of field, youthful atmosphere"
    if any(k in s for k in ("户外", "公园", "街头", "城市", "散步", "逛街", "出行")):
        return "lush outdoor park or urban street, golden hour natural light, soft bokeh"
    if any(k in s for k in ("旅行", "出游", "旅游", "travel", "trip")):
        return "scenic travel destination, open air, natural bright light, wanderlust vibe"
    if any(k in s for k in ("咖啡", "下午茶", "café", "coffee")):
        return "cozy café interior, wooden table, warm natural window light, lifestyle mood"
    # ── 非服装/家居/电器 场景 ──
    if any(k in s for k in ("客厅", "沙发", "起居", "living room")):
        return "bright modern living room, clean sofa and wooden floor, warm natural light"
    if any(k in s for k in ("厨房", "餐厅", "烹饪", "kitchen")):
        return "clean modern kitchen counter, marble surface, soft overhead lighting"
    if any(k in s for k in ("书房", "书桌", "学习", "阅读", "study", "desk")):
        return "tidy home study room, wooden desk, soft warm desk lamp, bookshelf background"
    if any(k in s for k in ("办公桌", "工作台", "workspace")):
        return "minimalist office desk setup, clean workspace, natural window light"
    if any(k in s for k in ("床头", "睡前", "bedside")):
        return "serene bedroom setting, bedside table, soft ambient lamp glow"
    if any(k in s for k in ("清洁", "打扫", "吸尘", "拖地", "clean")):
        return "bright clean home interior, polished floor, natural daylight, tidying scene"
    if any(k in s for k in ("装修", "家装", "布置", "decor", "interior")):
        return "stylish home interior during decoration, warm ambient light, modern furniture"
    if any(k in s for k in ("庭院", "花园", "园艺", "garden", "outdoor work", "户外劳作")):
        return "sunlit backyard garden, lush green plants, natural bright outdoor daylight"
    # ── 类别兜底（scene 词模糊时按 product_type 给默认场景）──
    pt = product_type.lower()
    if any(k in pt for k in ("家居", "home", "furniture", "家具")):
        return "bright Scandinavian-style living room, clean surfaces, warm natural light"
    if any(k in pt for k in ("3c", "数码", "电器", "electronics", "appliance")):
        return "clean minimalist workspace or kitchen counter, soft studio-style lighting"
    if any(k in pt for k in ("美妆", "beauty", "cosmetic", "护肤")):
        return "elegant vanity desk, soft diffused light, fresh white background, beauty mood"
    if any(k in pt for k in ("食品", "food", "零食", "beverage")):
        return "warm kitchen countertop with natural ingredients, rustic wooden surface, fresh daylight"
    # 全局默认
    return "bright authentic lifestyle setting, natural light, shallow depth of field"
