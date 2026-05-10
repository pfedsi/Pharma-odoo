from odoo import models, fields, api
from odoo.exceptions import UserError
import subprocess, logging, psycopg2, secrets, string
from datetime import date
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

def _generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(chars) for _ in range(length))

class SaasClient(models.Model):
    _name = 'saas.client'
    _description = 'Client SaaS Pharmacie'

    # ── Informations pharmacie ────────────────────────────────
    name        = fields.Char('Nom pharmacie', required=True)
    db_name     = fields.Char('Nom base de données', required=True)
    phone       = fields.Char('Téléphone', required=True)
    address     = fields.Char('Adresse')
    city        = fields.Char('Ville')
    responsible = fields.Char('Responsable')

    # ── Compte admin ─────────────────────────────────────────
    admin_email    = fields.Char('Email admin', required=True)
    admin_password = fields.Char(
        'Mot de passe',
        default=lambda self: _generate_password(),
        groups='base.group_system'
    )
    mail_sent  = fields.Boolean('Email envoyé', default=False, readonly=True)
    mail_error = fields.Char('Remarque email', readonly=True)

    # ── Toggle affichage MDP ──────────────────────────────────
    # store=True obligatoire : survit au reload de la page
    show_password = fields.Boolean(
        string='Afficher le mot de passe',
        default=False,
        store=True,
    )

    def action_toggle_password(self):
        self.ensure_one()
        self.show_password = not self.show_password

    # ── État création ─────────────────────────────────────────
    state = fields.Selection([
        ('draft',    'Brouillon'),
        ('creating', 'Création en cours'),
        ('done',     'Créé'),
        ('failed',   'Erreur'),
    ], default='draft')

    subdomain  = fields.Char(compute='_compute_subdomain', store=True)
    access_url = fields.Char(compute='_compute_access_url', store=True)

    # ── Abonnement ────────────────────────────────────────────
    subscription_end    = fields.Date("Abonnement jusqu'au")
    subscription_months = fields.Integer('Ajouter (mois)', default=1)
    subscription = fields.Selection([
        ('active',    'Actif'),
        ('suspended', 'Suspendu'),
    ], default='suspended', string='État abonnement', readonly=True)

    notes = fields.Text('Notes internes')

    # ── Computed ─────────────────────────────────────────────
    @api.depends('db_name', 'name')
    def _compute_subdomain(self):
        for r in self:
            raw = (r.db_name or r.name or '').lower().replace(' ', '-')
            for o, n in [('é','e'),('è','e'),('ê','e'),
                         ('à','a'),('ù','u'),('ô','o')]:
                raw = raw.replace(o, n)
            r.subdomain = ''.join(
                c for c in raw if c.isalnum() or c == '-'
            )

    @api.depends('subdomain')
    def _compute_access_url(self):
        for r in self:
            r.access_url = (
                f"https://{r.subdomain}.demopharma.eprswarm.com"
                if r.subdomain else False
            )

    # ── Abonnement ───────────────────────────────────────────
    def _apply_months(self, months):
        base = (
            self.subscription_end
            if self.subscription_end and self.subscription_end >= date.today()
            else date.today()
        )
        self.subscription_end = base + relativedelta(months=months)
        self.subscription = 'active'
        self._restore_db_access()
        self._send_email_confirmation()

    def action_set_subscription(self):
        """Bouton Appliquer — calcule la date, et réactive si base existante."""
        self.ensure_one()
        months = self.subscription_months or 1
        base = (
            self.subscription_end
            if self.subscription_end and self.subscription_end >= date.today()
            else date.today()
        )
        self.subscription_end = base + relativedelta(months=months)
        if self.state == 'done':
            self.subscription = 'active'
            self._restore_db_access()
            self._send_email_confirmation()

    def action_extend_1_month(self):
        self.ensure_one()
        self._apply_months(1)

    def action_extend_3_months(self):
        self.ensure_one()
        self._apply_months(3)

    def action_extend_6_months(self):
        self.ensure_one()
        self._apply_months(6)

    def action_suspend_manual(self):
        self.ensure_one()
        self.subscription = 'suspended'
        self._block_db_access()

    def action_open_url(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.access_url,
            'target': 'new',
        }

    # ── Création pharmacie ───────────────────────────────────
    def action_create_pharmacy(self):
        self.ensure_one()

        if not self.db_name or not self.admin_email:
            raise UserError("Nom de base et email admin requis.")
        if not self.subscription_end:
            raise UserError(
                "Saisissez la date de fin d'abonnement ou utilisez "
                "le champ mois + bouton Appliquer."
            )
        if not self.admin_password:
            self.admin_password = _generate_password()

        try:
            self.state = 'creating'
            self.env.cr.commit()

            # 1. Créer la base PostgreSQL
            r = subprocess.run(
                ['sudo', '-u', 'odoo', 'createdb', '-O', 'odoo', self.db_name],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                raise Exception(f"createdb: {r.stderr}")

            # 2. Initialiser Odoo
            subprocess.run([
                'sudo', '-u', 'odoo', '/usr/bin/odoo',
                '--config', '/etc/odoo/odoo.conf',
                '--database', self.db_name,
                '--init', 'base,mail',
                '--stop-after-init', '--no-http',
            ], capture_output=True, text=True, timeout=600)

            # 3. Credentials admin
            self._set_admin_credentials()

            # 4. Activer
            self.subscription = 'active'
            self.state = 'done'
            self.env.cr.commit()

            # 5. Email de bienvenue → envoyé au client
            self._send_email_welcome()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pharmacie créée !',
                    'message': (
                        f"Actif jusqu'au {self.subscription_end} — "
                        + ('Email envoyé au client.' if self.mail_sent
                           else 'ATTENTION: email non envoyé, voir remarque.')
                    ),
                    'type': 'success' if self.mail_sent else 'warning',
                    'sticky': True,
                }
            }

        except Exception as e:
            self.state = 'failed'
            self.env.cr.rollback()
            raise UserError(str(e))

    # ── Cron ─────────────────────────────────────────────────
    def _cron_check_subscriptions(self):
        today = date.today()
        for client in self.search([('state', '=', 'done')]):
            if not client.subscription_end:
                continue
            days_left = (client.subscription_end - today).days
            if days_left == 7:
                client._send_email_reminder()
            if days_left < 0 and client.subscription == 'active':
                client.subscription = 'suspended'
                client._block_db_access()
                client._send_email_suspended()

    # ── DB access ────────────────────────────────────────────
    def _block_db_access(self):
        try:
            conn = psycopg2.connect(dbname=self.db_name, user='odoo',
                                    password='12345678', host='localhost', port=5432)
            conn.autocommit = True
            conn.cursor().execute("UPDATE res_users SET active=false WHERE id != 1")
            conn.close()
            _logger.info(f"Acces bloque: {self.db_name}")
        except Exception as e:
            _logger.error(f"Erreur blocage: {e}")

    def _restore_db_access(self):
        try:
            conn = psycopg2.connect(dbname=self.db_name, user='odoo',
                                    password='12345678', host='localhost', port=5432)
            conn.autocommit = True
            conn.cursor().execute("UPDATE res_users SET active=true WHERE id != 1")
            conn.close()
            _logger.info(f"Acces restaure: {self.db_name}")
        except Exception as e:
            _logger.error(f"Erreur restauration: {e}")

    # ── Admin credentials ────────────────────────────────────
    def _set_admin_credentials(self):
        from passlib.hash import pbkdf2_sha512
        pw = pbkdf2_sha512.hash(self.admin_password)
        conn = psycopg2.connect(dbname=self.db_name, user='odoo',
                                password='12345678', host='localhost', port=5432)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("UPDATE res_users SET login=%s, password=%s WHERE id=2",
                    (self.admin_email, pw))
        cur.execute("""UPDATE res_partner SET email=%s, name=%s
                       WHERE id=(SELECT partner_id FROM res_users WHERE id=2)""",
                    (self.admin_email, self.name))
        conn.close()

    # ── Emails ───────────────────────────────────────────────
    def _mail(self, subject, body):
        try:
            self.env['mail.mail'].create({
                'subject': subject,
                'email_from': 'Q-Pharma TN <rayenzekri9@gmail.com>',
                'email_to': self.admin_email,
                'body_html': body,
            }).send()
            self.mail_sent = True
            self.mail_error = False
        except Exception as e:
            self.mail_sent = False
            self.mail_error = (
                f"Email non envoyé — donner manuellement : "
                f"URL={self.access_url} | Login={self.admin_email} | "
                f"MDP={self.admin_password} | Erreur: {str(e)}"
            )
            _logger.warning(f"Email non envoye: {e}")

    def _send_email_welcome(self):
        """Envoyé à la création — contient URL, login, MDP, date fin."""
        self._mail(
            subject=f'Votre espace Q-Pharma est prêt — {self.name}',
            body=f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#6c3483;padding:24px;text-align:center">
    <h1 style="color:white;margin:0;font-size:22px">Q-Pharma TN</h1>
    <p style="color:#e8daef;margin:4px 0;font-size:13px">Logiciel de gestion pharmacie</p>
  </div>
  <div style="padding:28px;background:#f9f9f9">
    <h2 style="color:#6c3483;margin-top:0">Bienvenue, {self.name} !</h2>
    <p>Votre espace de gestion est prêt. Voici vos identifiants :</p>
    <div style="background:white;border-left:4px solid #6c3483;
                padding:20px;margin:16px 0;border-radius:4px">
      <table style="width:100%;border-collapse:collapse">
        <tr>
          <td style="padding:10px 8px;color:#666;width:40%;border-bottom:1px solid #f0f0f0">URL</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0">
            <a href="{self.access_url}" style="color:#6c3483;font-weight:bold">{self.access_url}</a>
          </td>
        </tr>
        <tr>
          <td style="padding:10px 8px;color:#666;border-bottom:1px solid #f0f0f0">Email</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0">
            <strong>{self.admin_email}</strong>
          </td>
        </tr>
        <tr>
          <td style="padding:10px 8px;color:#666;border-bottom:1px solid #f0f0f0">Mot de passe</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0">
            <strong style="font-family:monospace;background:#f5f5f5;
                           padding:2px 8px;border-radius:3px">
              {self.admin_password}
            </strong>
          </td>
        </tr>
        <tr>
          <td style="padding:10px 8px;color:#666">Abonnement jusqu'au</td>
          <td style="padding:10px 8px"><strong>{self.subscription_end}</strong></td>
        </tr>
      </table>
    </div>
    <div style="text-align:center;margin:28px 0">
      <a href="{self.access_url}"
         style="background:#6c3483;color:white;padding:14px 36px;
                text-decoration:none;border-radius:4px;font-size:15px">
        Accéder à mon espace
      </a>
    </div>
    <p style="color:#e74c3c;font-size:12px;text-align:center">
      ⚠ Changez votre mot de passe après la première connexion.
    </p>
  </div>
  <div style="background:#6c3483;padding:14px;text-align:center">
    <p style="color:#e8daef;margin:0;font-size:12px">Support : rayenzekri9@gmail.com</p>
  </div>
</div>"""
        )

    def _send_email_confirmation(self):
        """Envoyé à chaque renouvellement."""
        self._mail(
            subject=f'Abonnement renouvelé — {self.name}',
            body=f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#6c3483;padding:24px;text-align:center">
    <h1 style="color:white;margin:0;font-size:22px">Q-Pharma TN</h1>
  </div>
  <div style="padding:28px">
    <h2 style="color:#27ae60;margin-top:0">✅ Abonnement renouvelé</h2>
    <p>Bonjour <strong>{self.name}</strong>,</p>
    <p>Votre abonnement a été renouvelé avec succès.</p>
    <div style="background:#f9f9f9;border-left:4px solid #27ae60;
                padding:16px;margin:16px 0;border-radius:4px">
      <p style="margin:0"><strong>Actif jusqu'au :</strong> {self.subscription_end}</p>
      <p style="margin:8px 0 0">
        <strong>URL :</strong>
        <a href="{self.access_url}" style="color:#6c3483">{self.access_url}</a>
      </p>
    </div>
    <p style="color:#666;font-size:12px">Support : rayenzekri9@gmail.com</p>
  </div>
</div>"""
        )

    def _send_email_reminder(self):
        """Envoyé 7 jours avant expiration."""
        self._mail(
            subject=f'Abonnement expire dans 7 jours — {self.name}',
            body=f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#e67e22;padding:24px;text-align:center">
    <h1 style="color:white;margin:0;font-size:22px">⚠ Rappel renouvellement</h1>
  </div>
  <div style="padding:28px">
    <p>L'abonnement de <strong>{self.name}</strong> expire le
       <strong>{self.subscription_end}</strong>.</p>
    <p>Contactez-nous pour renouveler votre abonnement.</p>
    <p style="color:#666;font-size:12px">Support : rayenzekri9@gmail.com</p>
  </div>
</div>"""
        )

    def _send_email_suspended(self):
        """Envoyé à l'expiration de l'abonnement."""
        self._mail(
            subject=f'Accès suspendu — {self.name}',
            body=f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#c0392b;padding:24px;text-align:center">
    <h1 style="color:white;margin:0;font-size:22px">🔒 Accès suspendu</h1>
  </div>
  <div style="padding:28px">
    <p>L'abonnement de <strong>{self.name}</strong> a expiré
       le <strong>{self.subscription_end}</strong>.</p>
    <p>Vos données sont conservées. Contactez-nous pour réactiver.</p>
    <p style="color:#666;font-size:12px">Support : rayenzekri9@gmail.com</p>
  </div>
</div>"""
        )