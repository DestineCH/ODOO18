# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.tools import float_round
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FuelSaleController(http.Controller):
    
    # ---------------------------------------------------------
    # 1. CONSTANTES & CONFIGURATION
    # ---------------------------------------------------------
    PRODUCT_CODES = {
        'STANDARD': 'MAZOUT_STD',
        'DEGRESSIF': 'MAZOUT_DEG',
        'STANDARD_UL': 'MAZOUT_STD_UL',
        'DEGRESSIF_UL': 'MAZOUT_DEG_UL',
    }

    MIN_QTY = 500
    MAX_QTY = 3000
    SEUIL_DEGRESSIF = 2000

    POSTAL_CODE_TO_PRICELIST = {
        '4990': 6,
        '6960': 12,
    }

    ALLOWED_POSTAL_CODES = list(POSTAL_CODE_TO_PRICELIST.keys())
    DEFAULT_POSTAL_CODE = '4990'

    # ---------------------------------------------------------
    # 2. UTILITAIRES (Helpers)
    # ---------------------------------------------------------
    def _get_product_by_quantity(self, quantity, ul=False):
        if ul:
            code = self.PRODUCT_CODES['DEGRESSIF_UL'] if quantity >= self.SEUIL_DEGRESSIF else self.PRODUCT_CODES['STANDARD_UL']
        else:
            code = self.PRODUCT_CODES['DEGRESSIF'] if quantity >= self.SEUIL_DEGRESSIF else self.PRODUCT_CODES['STANDARD']

        product = request.env['product.product'].sudo().search([('default_code', '=', code)], limit=1)
        if not product:
            _logger.error("[ERREUR PRODUIT] Aucun produit trouvé pour default_code=%s", code)
        return product

    def _get_pricelist_for_postal(self, postal_code):
        if not postal_code:
            return None
        # Nettoyage du CP
        postal_code = str(postal_code).strip()
        if postal_code not in self.POSTAL_CODE_TO_PRICELIST:
            return None
        pid = self.POSTAL_CODE_TO_PRICELIST.get(postal_code)
        return request.env['product.pricelist'].sudo().browse(pid)

    def _calculate_price_for_pricelist(self, product, quantity, pricelist):
        partner = request.env.user.partner_id
        
        # _get_product_price_rule returns (price, rule_id) for pricelists
        try:
            price, rule_id = pricelist._get_product_price_rule(product, quantity, partner)
            rule = request.env['product.pricelist.item'].sudo().browse(rule_id)
        except Exception as e:
            _logger.warning("Erreur calcul pricelist: %s", e)
            rule = request.env['product.pricelist.item']

        base_price = float(product.lst_price or 0.0) # lst_price est plus sûr que list_price sur certaines versions
        
        if rule.exists() and rule.compute_price == 'fixed' and rule.fixed_price:
            unit_price = float(rule.fixed_price)
        elif rule.exists() and rule.compute_price == 'formula':
            discount = float(rule.price_discount or 0.0)
            surcharge = float(rule.price_surcharge or 0.0)
            unit_price = base_price * (1.0 - discount) + surcharge
        else:
            unit_price = base_price

        currency = pricelist.currency_id or request.website.currency_id
        total_price = unit_price * float(quantity)
        total_price_rounded = float_round(total_price, precision_digits=currency.decimal_places)

        formatted = request.env['ir.qweb.field.monetary'].value_to_html(
            total_price_rounded, {'widget': 'monetary', 'display_currency': currency}
        )

        return {
            'unit_price': unit_price,
            'total_price': total_price_rounded,
            'formatted_price': formatted,
            'quantity': float(quantity),
        }

    def _create_fuel_order(self, partner, product_id, qty, postal_code):
        """ Méthode centralisée pour créer la commande """
        product = request.env['product.product'].sudo().browse(product_id)
        
        # 1. Déterminer la Pricelist correcte
        pricelist = self._get_pricelist_for_postal(postal_code)
        if not pricelist:
             # Fallback sur la default
             pid = self.POSTAL_CODE_TO_PRICELIST.get(self.DEFAULT_POSTAL_CODE)
             pricelist = request.env['product.pricelist'].sudo().browse(pid)

        # 2. Calculer le prix unitaire
        price_data = self._calculate_price_for_pricelist(product, qty, pricelist)
        unit_price = price_data.get('unit_price', product.lst_price)

        # 3. Créer la commande
        Order = request.env['sale.order'].sudo()
        order = Order.create({
            'partner_id': partner.id,
            'partner_invoice_id': partner.id,
            'partner_shipping_id': partner.id,
            'pricelist_id': pricelist.id, # Important : Lier la pricelist
        })

        # 4. Créer la ligne
        request.env['sale.order.line'].sudo().create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': qty,
            'price_unit': unit_price, # On force le prix calculé
        })
        
        # 5. Calculs totaux
        try:
            if hasattr(order, '_amount_all'):
                order._amount_all()
        except Exception as e:
            _logger.error("Erreur update montant commande: %s", e)
            
        return order

    # ---------------------------------------------------------
    # 3. ROUTES PAGE PRODUIT (GET)
    # ---------------------------------------------------------
    @http.route('/commande-03', type='http', auth='public', website=True)
    def commande_standard(self, **kw):
        default_qty = 1000.0
        product = self._get_product_by_quantity(default_qty, ul=False)
        
        # Sécurisation si le produit n'existe pas en DB
        if not product:
             return request.render("website.404")

        pricelist = self._get_pricelist_for_postal(self.DEFAULT_POSTAL_CODE) or request.env['product.pricelist'].sudo().browse(self.POSTAL_CODE_TO_PRICELIST[self.DEFAULT_POSTAL_CODE])
        price_data = self._calculate_price_for_pricelist(product, default_qty, pricelist)

        values = {
            'product': product,
            'current_price': price_data['formatted_price'],
            'default_postal_code': self.DEFAULT_POSTAL_CODE,
            'allowed_postal_codes': self.ALLOWED_POSTAL_CODES,
            'user_is_public': request.env.user._is_public(),
        }
        return request.render("prix.fuel_order_custom_template", values)

    @http.route('/commande-03u', type='http', auth='public', website=True)
    def commande_ultra(self, **kw):
        default_qty = 1000.0
        product = self._get_product_by_quantity(default_qty, ul=True)
        
        if not product:
             return request.render("website.404")

        pricelist = self._get_pricelist_for_postal(self.DEFAULT_POSTAL_CODE) or request.env['product.pricelist'].sudo().browse(self.POSTAL_CODE_TO_PRICELIST[self.DEFAULT_POSTAL_CODE])
        price_data = self._calculate_price_for_pricelist(product, default_qty, pricelist)

        values = {
            'product': product,
            'current_price': price_data['formatted_price'],
            'default_postal_code': self.DEFAULT_POSTAL_CODE,
            'allowed_postal_codes': self.ALLOWED_POSTAL_CODES,
            'user_is_public': request.env.user._is_public(),
        }
        return request.render("prix.fuel_order_ultra_template", values)

    # ---------------------------------------------------------
    # 4. ROUTE AJAX (Prix dynamique)
    # ---------------------------------------------------------
    @http.route('/shop/fuel_price_update', type='json', auth='public', website=True)
    def fuel_price_update(self, product_id=None, quantity=None, postal_code=None, ul=False, **kw):
        try:
            qty = float(quantity)
        except (ValueError, TypeError):
            return {'error': "Quantité invalide.", 'error_type': 'quantity'}

        if qty < self.MIN_QTY or qty > self.MAX_QTY:
            return {'error': f"Quantité entre {self.MIN_QTY}L et {self.MAX_QTY}L requise.", 'error_type': 'quantity'}

        pricelist = self._get_pricelist_for_postal(postal_code)
        if not pricelist:
            return {'error': "Code postal non desservi ou invalide.", 'error_type': 'postal_code'}

        product = self._get_product_by_quantity(qty, ul=ul)
        if not product:
            return {'error': 'Produit introuvable.', 'error_type': 'generic'}

        price_data = self._calculate_price_for_pricelist(product, qty, pricelist)
        price_data.update({'product_id': product.id, 'error_type': 'none'})
        return price_data

    # ---------------------------------------------------------
    # 5. CREATE ORDER (Utilisateur connecté)
    # ---------------------------------------------------------
    @http.route('/mazout/create_order', type='http', auth='user', website=True, methods=['POST'])
    def create_order(self, product_id=None, fuel_quantity=None, postal_code=None, **kwargs):
        try:
            pid = int(product_id)
            qty = float(fuel_quantity or 0.0)
        except (TypeError, ValueError):
            return request.redirect('/commande-03')

        postal_code = (postal_code or '').strip() or self.DEFAULT_POSTAL_CODE
        partner = request.env.user.partner_id

        # Appel de la logique centralisée
        try:
            order = self._create_fuel_order(partner, pid, qty, postal_code)
        except Exception as e:
            _logger.exception("Erreur create_order user connecté: %s", e)
            return request.redirect('/shop/cart') # Fallback

        request.session['sale_order_id'] = order.id
        request.session['sale_last_order_id'] = order.id
        return request.redirect('/shop/checkout')

    # ---------------------------------------------------------
    # 6. SIGNUP + ORDER (Nouveau client)
    # ---------------------------------------------------------
    @http.route('/mazout/signup_with_address', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def signup_with_address(self, **kw):
        # --- GET : Affichage ---
        if request.httprequest.method == 'GET':
            values = {
                'product_id': kw.get('product_id'),
                'fuel_quantity': kw.get('fuel_quantity'),
                'postal_code': kw.get('postal_code'),
                'ul': kw.get('ul'),
                'default_zip': kw.get('postal_code') or self.DEFAULT_POSTAL_CODE,
                'error': kw.get('error'), 
            }
            return request.render('prix.mazout_signup_template', values)

        # --- POST : Traitement ---
        email = (kw.get('email') or '').strip().lower()
        name = kw.get('name') or 'Client'
        password = kw.get('password')
        phone = kw.get('phone') # Nouveau champ
        
        if not email or not password or not phone:
            return self.signup_with_address(error="Tous les champs (Email, Pass, Tél) sont requis.", **kw)

        Users = request.env['res.users'].sudo()

        # 1. Check existence
        if Users.search([('login', '=', email)], limit=1):
            return request.redirect('/web/login?login=%s' % email)

        # 2. Création Partner
        Partner = request.env['res.partner'].sudo()
        country_be = request.env['res.country'].sudo().search([('code', '=', 'BE')], limit=1)
        
        partner_vals = {
            'name': name,
            'email': email,
            'phone': phone,
            'street': kw.get('street'),
            'zip': kw.get('zip') or kw.get('postal_code'),
            'city': kw.get('city'),
            'country_id': country_be.id if country_be else False,
            'customer_rank': 1,
        }
        
        try:
            partner = Partner.create(partner_vals)
        except Exception as e:
             _logger.error("Erreur création partner: %s", e)
             return self.signup_with_address(error="Erreur adresse invalide.", **kw)

        # 3. Création User
        group_portal = request.env.ref('base.group_portal')
        user_vals = {
            'name': name,
            'login': email,
            'partner_id': partner.id,
            'password': password,
            'groups_id': [(6, 0, [group_portal.id])],
            'active': True,
        }

        try:
            user = Users.with_context(no_reset_password=True).create(user_vals)
        except Exception as e:
            _logger.exception("Erreur création user: %s", e)
            return self.signup_with_address(error="Erreur technique création compte.", **kw)

        request.env.cr.commit()

        # 4. Auth
        try:
            uid = request.session.authenticate(destine, email, password)
        except Exception as e:
            _logger.error("Erreur authentification: %s", e)

        # 5. Commande
        try:
            pid = int(kw.get('product_id'))
            qty = float(kw.get('fuel_quantity') or 0.0)
            p_code = partner.zip or self.DEFAULT_POSTAL_CODE
            
            order = self._create_fuel_order(partner, pid, qty, p_code)
            
            request.session['sale_order_id'] = order.id
            request.session['sale_last_order_id'] = order.id
            
            return request.redirect('/shop/checkout')
            
        except Exception as e:
             _logger.exception("Erreur create_order post-signup: %s", e)
             return request.redirect('/shop/cart')