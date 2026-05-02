# -*- coding: utf-8 -*-
"""
migrations/19.0.1.1.0/post_migrate.py
"""
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("=== [PHARMACIE] Migration 19.0.1.1.0 — Fix médicaments storables ===")

    # ── 1. Vérifier que la colonne is_medicament existe ──────────────
    cr.execute("""
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name = 'product_template'
          AND column_name = 'is_medicament'
    """)
    if cr.fetchone()[0] == 0:
        _logger.warning("[PHARMACIE] Colonne is_medicament absente — migration ignorée.")
        return

    # ── 2. Vérifier que available_in_pos existe ───────────────────────
    cr.execute("""
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name = 'product_template'
          AND column_name = 'available_in_pos'
    """)
    has_available_in_pos = cr.fetchone()[0] > 0

    # ── 3. Fix type product ───────────────────────────────────────────
    try:
        cr.execute("""
            SELECT COUNT(*)
            FROM product_template
            WHERE is_medicament = TRUE
              AND type != 'product'
        """)
        count_bad = cr.fetchone()[0]
        _logger.info("[PHARMACIE] %d médicament(s) à corriger (type)", count_bad)

        if count_bad > 0:
            if has_available_in_pos:
                cr.execute("""
                    UPDATE product_template
                    SET
                        type             = 'product',
                        available_in_pos = TRUE,
                        sale_ok          = TRUE,
                        purchase_ok      = TRUE
                    WHERE is_medicament = TRUE
                      AND type != 'product'
                    RETURNING id, name, type
                """)
            else:
                cr.execute("""
                    UPDATE product_template
                    SET
                        type        = 'product',
                        sale_ok     = TRUE,
                        purchase_ok = TRUE
                    WHERE is_medicament = TRUE
                      AND type != 'product'
                    RETURNING id, name, type
                """)
            rows = cr.fetchall()
            for row_id, row_name, old_type in rows:
                _logger.info(
                    "[PHARMACIE] Corrigé [%d] %-40s  (%s → product)",
                    row_id, row_name or "?", old_type,
                )
    except Exception as e:
        _logger.error("[PHARMACIE] Erreur fix type product : %s", e)

    # ── 4. Fix quants négatifs ────────────────────────────────────────
    try:
        cr.execute("""
            SELECT COUNT(*)
            FROM stock_quant sq
            JOIN product_product pp ON pp.id = sq.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE pt.is_medicament = TRUE
              AND sq.quantity < 0
        """)
        count_neg = cr.fetchone()[0]
        _logger.info("[PHARMACIE] %d quant(s) négatif(s) à corriger", count_neg)

        if count_neg > 0:
            cr.execute("""
                UPDATE stock_quant sq
                SET quantity          = 0,
                    reserved_quantity = 0
                FROM product_product pp
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE sq.product_id = pp.id
                  AND pt.is_medicament = TRUE
                  AND sq.quantity < 0
                RETURNING sq.id, sq.product_id, sq.quantity
            """)
            neg_rows = cr.fetchall()
            for qid, pid, qty in neg_rows:
                _logger.info(
                    "[PHARMACIE] Quant [%d] produit [%d] : %s → 0",
                    qid, pid, qty,
                )
    except Exception as e:
        _logger.error("[PHARMACIE] Erreur fix quants négatifs : %s", e)

    # ── 5. Fix stock_quant sur locations non-internes ─────────────────
    # Nettoyer les quants parasites (Vendors, Customers, Inventory adjustment)
    # qui faussent les calculs de stock
    try:
        cr.execute("""
            SELECT COUNT(sq.id)
            FROM stock_quant sq
            JOIN stock_location sl ON sl.id = sq.location_id
            JOIN product_product pp ON pp.id = sq.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE pt.is_medicament = TRUE
              AND sl.usage NOT IN ('internal', 'transit')
              AND sq.quantity != 0
        """)
        count_parasite = cr.fetchone()[0]
        _logger.info("[PHARMACIE] %d quant(s) parasite(s) sur locations non-internes", count_parasite)

        if count_parasite > 0:
            cr.execute("""
                UPDATE stock_quant sq
                SET quantity          = 0,
                    reserved_quantity = 0
                FROM stock_location sl,
                     product_product pp,
                     product_template pt
                WHERE sq.location_id  = sl.id
                  AND sq.product_id   = pp.id
                  AND pp.product_tmpl_id = pt.id
                  AND pt.is_medicament   = TRUE
                  AND sl.usage NOT IN ('internal', 'transit')
                  AND sq.quantity != 0
                RETURNING sq.id, sl.usage, sq.quantity
            """)
            parasite_rows = cr.fetchall()
            for qid, usage, qty in parasite_rows:
                _logger.info(
                    "[PHARMACIE] Quant parasite [%d] usage=%s qty=%s → 0",
                    qid, usage, qty,
                )
    except Exception as e:
        _logger.error("[PHARMACIE] Erreur fix quants parasites : %s", e)

    # ── 6. Vérification finale ────────────────────────────────────────
    try:
        cr.execute("""
            SELECT COUNT(*)
            FROM product_template
            WHERE is_medicament = TRUE
              AND type != 'product'
        """)
        remaining = cr.fetchone()[0]

        if remaining == 0:
            _logger.info("[PHARMACIE] ✓ Migration terminée. Stock et POS opérationnels.")
        else:
            _logger.warning(
                "[PHARMACIE] ⚠ %d médicament(s) encore mal configuré(s) !",
                remaining,
            )
    except Exception as e:
        _logger.error("[PHARMACIE] Erreur vérification finale : %s", e)