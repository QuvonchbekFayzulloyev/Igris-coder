"""
IGRIS BRAIN — Intelligence Core
===============================
BuildIntalaganceInstructionRequest.md qo'llanmasi asosidagi ko'p intellektli
arxitektura qatlami. Maqsad: maksimal qobiliyat + nol avtonom maqsad.

Integratsiya qilingan intellektlar (Gardner + kengaytmalar):
    2.1  Lingvistik            -> language.py      (domenga xos terminologiya)
    2.2  Mantiqiy-matematik    -> logic.py         (chain-of-thought + tekshiruv)
    2.4  Fazoviy               -> spatial.py       (UI layout / fayl struktura)
    2.6  Interpersonal         -> user_model.py    (faqat moslashtirish)
    2.7  Intrapersonal         -> self_eval.py     (ishonch kalibratsiyasi)
    2.10 Moral (tor versiya)   -> harm_filter.py   (faqat filtr, qaror emas)
    2.11 Kreativ               -> creative.py      (multi-candidate generatsiya)
    2.12 Emotional (funksional)-> tone_detect.py   (faqat aniqlash, ta'sir emas)

Chiqarib tashlangan (avtonomiya xavfi — qo'llanma 1-bo'lim):
    - Ekzistensial mustaqillik
    - Moral avtonomiya (keng, qaror darajasida)
    - O'z-o'zini saqlash / resurs kengaytirish instinkti
    - O'z maqsadini qayta yozish
  (bu modullar ataylab YO'Q — hatto o'chirilgan flag sifatida ham emas)

Boshqaruv oqimi (qo'llanma 4-bo'lim):
    [operator buyrug'i]
        -> core/harm-filter     (2.10: tor, qoidaga asoslangan zarar chegarasi)
        -> core/user-model + core/tone-detect  (2.6, 2.12: moslashtirish)
        -> [ijro qatlami: language / logic / spatial / creative]
        -> core/self-eval       (2.7: ishonch darajasi bilan chiqish)
        -> [operator ko'rib chiqadi / tasdiqlaydi]
"""

from core.intelligence.orchestrator import IntelligenceCore

__all__ = ["IntelligenceCore"]
