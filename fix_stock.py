#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("\n" + "="*60)
print("  DIAGNOSTIC STOCK MEDICAMENTS")
print("="*60)

# 1. Verifier le type reel en base
env.cr.execute("""
    SELECT id, name, type, available_in_pos, sale_ok
    FROM product_template
    WHERE is_medicament = TRUE
    ORDER BY id
""")
rows = env.cr.fetchall()
print("\n%d medicament(s) trouves :\n" % len(rows))
for r in rows:
    pid, name, ptype, pos, sale = r
    flag = "OK" if ptype == "product" else "MAUVAIS"
    nom = (name or "")[:40]
    print("  [%d] %-10s %-10s %s" % (pid, ptype, flag, nom))

# 2. Verifier stock.quant
env.cr.execute("""
    SELECT pt.id, pt.name, pt.type,
           COALESCE(SUM(sq.quantity), 0) as qty
    FROM product_template pt
    LEFT JOIN product_product pp ON pp.product_tmpl_id = pt.id
    LEFT JOIN stock_quant sq ON sq.product_id = pp.id
        AND sq.location_id IN (
            SELECT id FROM stock_location WHERE usage = 'internal'
        )
    WHERE pt.is_medicament = TRUE
    GROUP BY pt.id, pt.name, pt.type
    ORDER BY pt.id
""")
quant_rows = env.cr.fetchall()
print("\nStock reel (stock.quant) :")
for r in quant_rows:
    pid, name, ptype, qty = r
    nom = (name or "")[:40]
    print("  [%d] type=%-10s qty=%.2f  %s" % (pid, ptype, qty, nom))

# 3. Emplacements internes
env.cr.execute("""
    SELECT id, complete_name, usage
    FROM stock_location
    WHERE usage = 'internal' AND active = TRUE
    ORDER BY id LIMIT 10
""")
locs = env.cr.fetchall()
print("\nEmplacements internes :")
for loc in locs:
    print("  [%d] %s" % (loc[0], loc[1] or ""))

# 4. CORRECTION
print("\n" + "="*60)
print("  CORRECTION EN COURS...")
print("="*60)

env.cr.execute("""
    UPDATE product_template
    SET type = 'product',
        available_in_pos = TRUE,
        sale_ok = TRUE,
        purchase_ok = TRUE
    WHERE is_medicament = TRUE
    RETURNING id, name
""")
fixed = env.cr.fetchall()
print("\n%d produit(s) corrige(s) :" % len(fixed))
for fid, fname in fixed:
    print("  [%d] %s" % (fid, fname or ""))

# 5. Reactiver variantes
env.cr.execute("""
    UPDATE product_product pp
    SET active = TRUE
    FROM product_template pt
    WHERE pp.product_tmpl_id = pt.id
      AND pt.is_medicament = TRUE
      AND pp.active = FALSE
    RETURNING pp.id
""")
variants = env.cr.fetchall()
if variants:
    print("\n%d variante(s) reactivee(s)" % len(variants))

# 6. Commit
env.cr.commit()
print("\nCOMMIT OK - redemarrer Odoo pour vider le cache")
print("="*60 + "\n")