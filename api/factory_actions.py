"""Operational decisions that add audit history without changing posted stock or tax."""
from datetime import date
from sqlalchemy import select, update
from api import database
from api.native import authorize, factory_lock, insert_row, table, audit, now, required_integer, lots
from api.sales.services import get_row, outstanding


# Hold or release the remaining finished-goods lot under the factory lock.
def quality(data, user):
    authorize(user, ['admin', 'production'])
    lot_id = required_integer(data['lot'], 1)
    status, reason = data['status'], data['reason'].strip()
    if status not in ('held', 'released') or not reason:
        raise ValueError('Quality decision and reason required.')
    with database.transaction() as conn:
        factory_lock(conn)
        lot = get_row(conn, 'inventory_stocklot', lot_id)
        item = get_row(conn, 'inventory_item', lot['item_id'])
        if item['category'] != 'finished':
            raise ValueError('Quality decisions are for finished goods.')
        if not any(row['id'] == lot_id and row['quantity'] > 0 for row in lots(conn, item['id'])):
            raise ValueError('Lot has no remaining stock.')
        target = table(conn, 'factory_qualityhold')
        old = conn.execute(select(target).where(target.c.lot_id == lot_id)).mappings().first()
        if old and (old['status'], old['reason']) == (status, reason):
            return old['id']
        if status == 'released' and (not old or old['status'] != 'held'):
            raise ValueError('Only a held lot can be released.')
        before = {'status': old['status'], 'reason': old['reason']} if old else {}
        if old:
            conn.execute(update(target).where(target.c.id == old['id']).values(status=status, reason=reason, actor_id=user['id'], changed_at=now()))
            identifier = old['id']
        else:
            identifier = insert_row(conn, 'factory_qualityhold', lot_id=lot_id, status=status, reason=reason, actor_id=user['id'], changed_at=now())
        audit(conn, user, 'quality.' + status, 'inventory.StockLot', lot_id, before, {'status': status, 'reason': reason})
        return identifier


# Explain a completed run's shortfall without altering its immutable issue/output events.
def loss_note(data, user, key):
    authorize(user, ['admin', 'production'])
    run_id = required_integer(data['run'], 1)
    reason, note = data['reason'].strip(), data.get('note', '').strip()
    if not key or not reason or not note:
        raise ValueError('Loss reason, explanation and request key required.')
    with database.transaction() as conn:
        factory_lock(conn)
        run = get_row(conn, 'production_productionrun', run_id)
        if run['state'] != 'completed':
            raise ValueError('Only completed runs can receive loss notes.')
        target = table(conn, 'factory_lossnote')
        old = conn.execute(select(target).where(target.c.request_key == key)).mappings().first()
        if old:
            if (old['run_id'], old['reason'], old['note'], old['actor_id']) != (run_id, reason, note, user['id']):
                raise ValueError('Loss note retry conflicts.')
            return old['id']
        identifier = insert_row(conn, 'factory_lossnote', run_id=run_id, reason=reason, note=note, actor_id=user['id'], recorded_at=now(), request_key=key)
        audit(conn, user, 'run.loss_note', 'production.ProductionRun', run_id, {}, {'reason': reason, 'note': note})
        return identifier


# Record a collection attempt and next contact date against an unpaid invoice.
def followup(data, user, key):
    authorize(user, ['admin'])
    invoice_id = required_integer(data['invoice'], 1)
    note, next_contact = data['note'].strip(), date.fromisoformat(data['next_contact'])
    if not note or not key:
        raise ValueError('Follow-up note and request key required.')
    with database.transaction() as conn:
        factory_lock(conn)
        invoice = get_row(conn, 'sales_invoice', invoice_id)
        target = table(conn, 'factory_collectionfollowup')
        old = conn.execute(select(target).where(target.c.request_key == key)).mappings().first()
        if old:
            if (old['invoice_id'], old['note'], old['next_contact'], old['actor_id']) != (invoice_id, note, next_contact, user['id']):
                raise ValueError('Follow-up retry conflicts.')
            return old['id']
        if invoice['status'] != 'posted' or outstanding(conn, invoice) <= 0:
            raise ValueError('Follow-up requires an outstanding invoice.')
        identifier = insert_row(conn, 'factory_collectionfollowup', invoice_id=invoice_id, note=note, next_contact=next_contact, actor_id=user['id'], recorded_at=now(), request_key=key)
        audit(conn, user, 'collection.followup', 'sales.Invoice', invoice_id, {}, {'note': note, 'next_contact': str(next_contact)})
        return identifier
