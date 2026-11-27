"""Finite input-byte caps for the existing backup producer, not backup authority."""


class Budget:
    def __init__(self, *, original_bytes, control_bytes):
        for value in (original_bytes, control_bytes):
            if type(value) is not int or value < 0:
                raise ValueError('Explicit nonnegative backup input bounds required')
        self.original_limit = original_bytes
        self.control_limit = control_bytes
        self.original_used = 0
        self.control_used = 0

    def maximum_missing(self, requested_bytes):
        self._size(requested_bytes)
        return min(requested_bytes, self.original_limit - self.original_used)

    def original_captured(self, actual_bytes):
        self._size(actual_bytes)
        if self.original_used + actual_bytes > self.original_limit:
            raise ValueError('Original capture exceeded the admitted producer bound')
        self.original_used += actual_bytes

    def admit_control(self, input_bytes):
        self._size(input_bytes)
        if self.control_used + input_bytes > self.control_limit:
            raise ValueError('Control/closure capture exceeds remaining backup input bound')
        # Charge before writing; uncertain failed captures retain their charge.
        self.control_used += input_bytes

    def snapshot(self):
        return dict(original_input_limit=self.original_limit,
                    original_input_used=self.original_used,
                    control_input_limit=self.control_limit,
                    control_input_used=self.control_used)

    @staticmethod
    def _size(value):
        if type(value) is not int or value < 0:
            raise ValueError('Exact nonnegative byte count required')
