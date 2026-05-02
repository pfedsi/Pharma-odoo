import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['--config=/etc/odoo/odoo.conf'])
registry = odoo.registry(odoo.tools.config['db_name'])

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})

    print("=== 1. TYPE VUE ===")
    cr.execute("""
        SELECT relname, relkind
        FROM pg_class
        WHERE relname = 'report_stock_quantity'
    """)
    print(cr.fetchall())
    # v=vue normale, m=matérialisée, r=table

    print("\n=== 2. TRACKING MEDICAMENTS ===")
    cr.execute("""
        SELECT id, name->>'en_US', tracking
        FROM product_template
        WHERE is_medicament = TRUE
        ORDER BY id
    """)
    for r in cr.fetchall():
        print(r)

    print("\n=== 3. QUANTS REELS ===")
    cr.execute("""
        SELECT pt.id, pt.name->>'en_US', pt.tracking,
               COALESCE(SUM(sq.quantity), 0) AS stock
        FROM product_template pt
        JOIN product_product pp ON pp.product_tmpl_id = pt.id
        LEFT JOIN stock_quant sq ON sq.product_id = pp.id
            AND sq.location_id IN (
                SELECT id FROM stock_location WHERE usage = 'internal'
            )
        WHERE pt.is_medicament = TRUE
        GROUP BY pt.id, pt.name, pt.tracking
        ORDER BY stock DESC
    """)
    for r in cr.fetchall():
        print(r)

    print("\n=== 4. CONTENU VUE RAPPORT (médicaments) ===")
    cr.execute("""
        SELECT rsq.product_id, rsq.state, SUM(rsq.quantity)
        FROM report_stock_quantity rsq
        JOIN product_product pp ON pp.id = rsq.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE pt.is_medicament = TRUE
        GROUP BY rsq.product_id, rsq.state
        ORDER BY rsq.product_id
    """)
    rows = cr.fetchall()
    print(rows if rows else "VIDE — vue ne voit pas les médicaments")

    print("\n=== 5. DEFINITION VUE SQL ===")
    cr.execute("SELECT pg_get_viewdef('report_stock_quantity'::regclass, true)")
    print(cr.fetchone()[0])

    print("\n=== FIN — pas de commit ===")