odoo.define('risk_management.wkhtmltopdfFix', function (require) {
    // wkhtmltopdf 0.12.5 crash fix.
    // https://github.com/wkhtmltopdf/wkhtmltopdf/issues/3242#issuecomment-518099192
    'use strict';
    (function (setLineDash) {
        CanvasRenderingContext2D.prototype.setLineDash = function () {
            if (!arguments[0].length) {
                arguments[0] = [1, 0];
            }
            // Now, call the original method
            return setLineDash.apply(this, arguments);
        };
    })(CanvasRenderingContext2D.prototype.setLineDash);
    Function.prototype.bind = Function.prototype.bind || function (thisp) {
        var fn = this;
        return function () {
            return fn.apply(thisp, arguments);
        };
    };
});