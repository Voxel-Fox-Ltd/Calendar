from enum import Enum


__all__ = (
    'RepeatTime',
)


class RepeatTime(Enum):
    daily = 'daily'
    weekly = 'weekly'
    monthly = 'monthly'
    yearly = 'yearly'

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"
