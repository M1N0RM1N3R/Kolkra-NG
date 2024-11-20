from enum import Enum

from kolkra_ng.enums.by_name import by_name


@by_name
class StaffLevel(int, Enum):
    moderator = 1
    admin = 2
    head_admin = 3
    co_owner = 4
    owner = 5
