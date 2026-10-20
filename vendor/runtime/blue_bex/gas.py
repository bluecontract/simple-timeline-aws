"""Deterministic scalar gas meter. Compilation consumes no semantic gas."""
from dataclasses import dataclass, field
from .values import BexError

DEFAULT = dict(expressionBase=1, statementBase=1, documentRead=2, eventRead=1,
    stepsRead=1, currentContractRead=1, varRead=1, resultValueRead=2,
    pointerGetBase=1, pointerSetBase=3, objectSetBase=2, appendChangeBase=5,
    appendEventBase=5, forEachItem=1, functionCall=2, integerWork=1, textWork=1, valueMember=1, nodeIdentityRequested=5)

class GasExhausted(BexError):
    code = 'GAS_LIMIT_EXCEEDED'

@dataclass
class Gas:
    limit: int = 10000000
    used: int = 0
    rejected: dict | None = None
    schedule: dict = field(default_factory=lambda: dict(DEFAULT))
    owner: str = 'BEX'
    parent: 'Gas | None' = None

    def __post_init__(self):
        if type(self.limit) is not int: raise TypeError('gas limit must be Integer')
        if any(type(v) is not int or v < 0 for v in self.schedule.values()): raise ValueError('invalid tariff')

    def charge(self, counter: str, units: int = 1, *, amount: int | None = None):
        if self.rejected is not None: raise GasExhausted(self.rejected['counter'])
        if type(units) is not int or units < 0: raise BexError('invalid charge units')
        cost = self.schedule[counter] * units if amount is None else amount
        if type(cost) is not int or cost < 0: raise BexError('invalid charge amount')
        if self.limit >= 0 and self.used + cost > self.limit:
            self.rejected = dict(owner=self.owner, counter=counter, units=units, amount=cost, before=self.used,
                                 cap='LOCAL' if self.parent else 'SHARED', remaining=self.limit-self.used)
            if self.parent is not None:
                # Preserve the *local* rejection in the closure receipt without
                # falsely charging it as admitted parent work.
                self.parent.rejected = dict(self.rejected, before=self.parent.used, localBefore=self.used)
            raise GasExhausted(f'{counter}: next {cost}, remaining {self.limit-self.used}')
        if self.parent is not None:
            old = self.parent.owner
            self.parent.owner = self.owner
            try: self.parent.charge(counter, units, amount=cost)
            finally: self.parent.owner = old
        self.used += cost

    @property
    def attempted(self):
        return self.used + (0 if self.rejected is None else self.rejected['amount'])
