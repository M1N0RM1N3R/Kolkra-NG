from enum import Enum

from kolkra_ng.enums.by_name import by_name


@by_name
class StaffLevel(int, Enum):
    council = 1
    arbit = 2
    mod = 3
    admin = 4
    owner = 5
