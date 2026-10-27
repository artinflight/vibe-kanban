"""Internal receipt semantics after native_adapter validates the reviewed v2 wire response."""
import uuid


class ReviewedProtocolUnavailable(ValueError):
    pass


def normalize(result, batch_id, intent_sha256):
    """Only an actual reviewed adapter may supply positive no-admission evidence.

    HTTP status alone, an exception, or an empty/not-found lookup is never that evidence.
    These internal fields come from native_adapter.decode; fixtures test Store separately.
    """
    unknown = {'kind': 'unknown', 'reason': 'unconfirmed_delivery'}
    if (not isinstance(result, dict) or result.get('batch_id') != batch_id
            or result.get('intent_sha256') != intent_sha256):
        return unknown
    kind = result.get('kind')
    receipt = result.get('receipt_id')
    if kind not in {'accepted', 'deferred', 'rejected'} or not isinstance(receipt, str) or not 1 <= len(receipt) <= 200:
        return unknown
    if kind in {'deferred', 'rejected'} and result.get('definitely_not_admitted') is not True:
        return unknown
    if kind == 'accepted':
        try:
            execution_id = str(uuid.UUID(result['execution_id']))
        except (KeyError, ValueError, TypeError, AttributeError):
            return unknown
    else:
        execution_id = None
    # A reviewed adapter supplies a bounded enum reason, never a raw HTTP body/error.
    reason = result.get('reason', kind)
    if not isinstance(reason, str) or not reason.replace('_', '').isalnum() or len(reason) > 80:
        return unknown
    return {'kind': kind, 'execution_id': execution_id, 'receipt_id': receipt, 'reason': reason}
