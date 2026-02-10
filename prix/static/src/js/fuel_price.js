/** @odoo-module **/
/* global $ */

const debounce = (func, delay) => {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
};

$(document).ready(function() {
    'use strict';

    var $form = $('#custom_fuel_order_form');
    if ($form.length === 0) {
        return;
    }

    var DEBOUNCE_TIME = 100;

    var $quantityInput = $form.find('#fuel_quantity');
    var $postalCodeInput = $form.find('#postal_code_input');
    var $priceDisplay = $form.find('#dynamic_fuel_price');
    // bouton commander
    var $orderButton = $form.find('#go_to_order_button');
    var $quantityErrorDisplay = $form.find('#fuel_quantity_error');
    var $postalCodeErrorDisplay = $form.find('#postal_code_error');

    function resetErrors() {
        $quantityErrorDisplay.empty();
        $postalCodeErrorDisplay.addClass("d-none").empty();
    }

    var _callPriceUpdate = function () {

        resetErrors();
        $priceDisplay.html('<span style="color: grey;">--- Saisir CP et Qté ---</span>');
        $orderButton.prop('disabled', true);

        var quantity = parseFloat($quantityInput.val());
        var postalCode = ($postalCodeInput.val() || '').trim();
        var productId = $form.find('input[name="product_id"]').val();

        var validCPs = window.ALLOWED_POSTAL_CODES || [];

        if (!/^\d{4}$/.test(postalCode) || !validCPs.includes(postalCode)) {
            if (postalCode !== "") {
                $postalCodeErrorDisplay
                    .removeClass("d-none")
                    .html("Code postal invalide.");
            }
            return;
        }

        if (isNaN(quantity) || quantity <= 0) {
            return;
        }

        $priceDisplay.html('<i class="fa fa-spinner fa-spin"></i>');

        $.ajax({
            url: '/shop/fuel_price_update',
            type: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    product_id: parseInt(productId),
                    quantity: quantity,
                    postal_code: postalCode,
                    ul: window.IS_UL || false
                }
            }),
            success: function (response) {

                var data = response && response.result ? response.result : null;

                if (!data) {
                    console.error("Réponse serveur invalide:", response);
                    $priceDisplay.html('<span style="color:red;">Erreur serveur.</span>');
                    $orderButton.prop('disabled', true);
                    return;
                }

                if (data.error) {
                    $orderButton.prop('disabled', true);
                    $priceDisplay.html('---');

                    if (data.error_type === 'quantity') {
                        $quantityErrorDisplay.text(data.error);
                    }
                    else if (data.error_type === 'postal_code') {
                        $postalCodeErrorDisplay
                            .removeClass("d-none")
                            .html(data.error);
                    }
                    else {
                        $priceDisplay.html('<span style="color:red;">' + data.error + '</span>');
                    }
                    return;
                }

                if (data.formatted_price) {
                    $priceDisplay.html(data.formatted_price);
                    $form.find('.o_hidden_add_qty').val(data.quantity);
                    $form.find('input[name="product_id"]').val(data.product_id);
                    // enable order button and store values in data- attributes for redirect
                    $orderButton.prop('disabled', false);
                    $orderButton.data('product-id', data.product_id);
                    $orderButton.data('quantity', data.quantity);
                    $orderButton.data('postal-code', postalCode);
                    $orderButton.data('ul', window.IS_UL || false);
                }
            },
            error: function(xhr, status, error) {
                console.error("Erreur AJAX:", error);
                $priceDisplay.html('<span style="color:red;">Erreur serveur.</span>');
                $orderButton.prop('disabled', true);
            }
        });

    };

    var debouncedCall = debounce(_callPriceUpdate, DEBOUNCE_TIME);

    $quantityInput.on('input change', debouncedCall);
    $postalCodeInput.on('input change', debouncedCall);

    // Lier l'événement click (scope local)
    $orderButton.on('click', function (ev) {
        ev.preventDefault();

        // valeurs à envoyer
        var product_id = $(this).data('product-id') || $form.find('input[name="product_id"]').val();
        var quantity = $(this).data('quantity') || $form.find('.o_hidden_add_qty').val();
        var postal_code = $(this).data('postal-code') || $form.find('#postal_code_input').val();
        var ul = $(this).data('ul') || false;

        // window.USER_IS_PUBLIC doit être injecté depuis le template (true/false)
        var isPublic = (typeof window.USER_IS_PUBLIC !== 'undefined') ? (window.USER_IS_PUBLIC === true || window.USER_IS_PUBLIC === 'true') : true;

        if (isPublic) {
            // redirect to signup page that collects address, passing params by querystring
            var qs = '?product_id=' + encodeURIComponent(product_id) +
                     '&fuel_quantity=' + encodeURIComponent(quantity) +
                     '&postal_code=' + encodeURIComponent(postal_code) +
                     '&ul=' + encodeURIComponent(ul);
            window.location.href = '/mazout/signup_with_address' + qs;
        } else {
            // submit form to create order route (user logged in)
            $form.submit();
        }
    });

    // Premier calcul (si valeurs déjà présentes)
    _callPriceUpdate();
});
