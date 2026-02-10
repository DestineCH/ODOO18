# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests, re, logging
from io import BytesIO
from PyPDF2 import PdfReader

_logger = logging.getLogger(__name__)

SPF_URL = "https://economie.fgov.be/sites/default/files/Files/Energy/prices/Tarifs-officiels-produits-petroliers.pdf"


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    spf_last_update = fields.Datetime("Dernière mise à jour SPF", readonly=True)
    spf_source_url = fields.Char("Source SPF", readonly=True)
    spf_next_update_date = fields.Datetime("Prochaine mise à jour prévue", readonly=True)

    @api.model
    def _get_spf_prices(self):
        """Télécharge et extrait les prix mazout depuis le PDF du SPF"""
        try:
            response = requests.get(SPF_URL, timeout=10)
            response.raise_for_status()
            reader = PdfReader(BytesIO(response.content))
            text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())

            # Extraction des deux prix (<2000 et ≥2000)
            pattern = (
                r"Gasoil de chauffage\s*\(H0/H7\).*?moins de 2000 l l\s*([0-9]+,[0-9]+).*?"
                r"Gasoil de chauffage\s*\(H0/H7\).*?à partir de 2000 l l\s*([0-9]+,[0-9]+)"
            )
            match = re.search(pattern, text, re.S)
            if not match:
                _logger.warning("[SPF] Aucun prix détecté dans le PDF.")
                return None

            moins_2000 = float(match.group(1).replace(",", "."))
            plus_2000 = float(match.group(2).replace(",", "."))
            _logger.info("[SPF] Prix détectés : <2000L=%.4f / ≥2000L=%.4f", moins_2000, plus_2000)
            return moins_2000, plus_2000

        except Exception as e:
            _logger.exception("[SPF] Erreur lors du téléchargement ou de la lecture du PDF : %s", e)
            return None

    @api.model
    def sync_spf_fuel_prices(self):
        """Met à jour les prix mazout à partir du SPF"""
        _logger.info("[SPF] Téléchargement depuis %s", SPF_URL)
        prix = self._get_spf_prices()
        if not prix:
            _logger.warning("[SPF] Aucune donnée de prix trouvée.")
            return False

        prix_std, prix_deg = prix
        prix_std_ul = round(prix_std + 0.02, 4)
        prix_deg_ul = round(prix_deg + 0.02, 4)

        # 💡 mapping clair entre codes et prix
        mapping = {
            'MAZOUT_STD': prix_std,
            'MAZOUT_DEG': prix_deg,
            'MAZOUT_STD_UL': prix_std_ul,
            'MAZOUT_DEG_UL': prix_deg_ul,
        }

        for code, price in mapping.items():
            product = self.env['product.template'].search([
                ('default_code', '=', code),
            ], limit=1)

            if not product:
                _logger.warning("[SPF] Produit introuvable pour le code : %s", code)
                continue

            product.write({
                'list_price': price,
                'spf_last_update': fields.Datetime.now(),
                'spf_source_url': SPF_URL,
            })

            for variant in product.product_variant_ids:
                variant.write({'lst_price': price})
                _logger.info("[SPF] Variant %s (ID %s) mis à jour à %.4f €/L", variant.name, variant.id, price)

            self.env.flush_all()
            self.env.cr.commit()

            _logger.info("[SPF] Produit %s (ID %s) mis à jour à %.4f €/L", product.name, product.id, price)

        _logger.info("[SPF] Mise à jour réussie : <2000L=%.4f, ≥2000L=%.4f, UL <2000L=%.4f, UL ≥2000L=%.4f",
                     prix_std, prix_deg, prix_std_ul, prix_deg_ul)
        print(f"✅ Prix mis à jour et sauvegardés : "
              f"<2000L={prix_std}, ≥2000L={prix_deg}, UL<2000L={prix_std_ul}, UL≥2000L={prix_deg_ul}")
        return True
