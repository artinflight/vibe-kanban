# Strict review historical-format fixtures

`review-goal-sleep.jsonl` retains the notification shapes, millisecond values and
unsigned integer durations independently observed in Staging's four historical
reports. Thread/turn/call identifiers are replaced with disposable names. There
is no report content, credential or user review evidence in this fixture.

Positive and damaged-variant tests use the strict pre-normalization validator.
The real HTTP/recovery tests write these events before a disposable final reply,
then run the storage writer, strict reader, normalizer, identity reducer and
conditional receipt route. Unknown native methods/items remain rejected by the
pinned SDK parser. This fixture does not certify any historical writer closure.
