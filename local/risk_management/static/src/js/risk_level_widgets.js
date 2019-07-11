odoo.define('risk_management.progress_bar', function (require) {
    'use strict';
    var basic_fields = require('web.basic_fields');
    var core = require('web.core');
    var utils = require('web.utils');
    var ProgressBar = basic_fields.FieldProgressBar;
    var _t = core._t;

    ProgressBar.include({
        init: function () {
            this._super.apply(this, arguments);

            // the progressbar needs the values and not the field name, passed in options
            if (this.recordData[this.nodeOptions.current_value]) {
                this.value = this.recordData[this.nodeOptions.current_value];
            }
            this.max_value = this.recordData[this.nodeOptions.max_value] || 100;

            // the ref_value is the value that the widget uses to determine its color
            this.ref_value = this.recordData[this.nodeOptions.ref_value] || 100;
            this.risk_type = this.recordData['risk_type'] || false;
            this.readonly = this.nodeOptions.readonly || !this.nodeOptions.editable;
            this.edit_max_value = this.nodeOptions.edit_max_value || false;
            this.title = _t(this.attrs.title || this.nodeOptions.title) || '';
            this.edit_on_click = !this.nodeOptions.edit_max_value || false;

            this.write_mode = false;
        },

        _render_value: function (v) {
            var value = this.value;
            var max_value = this.max_value;
            var ref_value = this.ref_value;
            var risk_type = this.risk_type
            if (!isNaN(v)) {
                if (this.edit_max_value) {
                    max_value = v;
                } else {
                    value = v;
                }
            }
            value = value || 0;
            max_value = max_value || 0;

            var widthComplete;
            if (value <= max_value) {
                widthComplete = value / max_value * 100;
            } else {
                widthComplete = 100;
            }

            this.$('.o_progress').toggleClass('o_progress_overflow', value > max_value);
            if (risk_type === 'O') {
                this.$('.o_progressbar_complete').toggleClass('o_progress_acceptable', value > ref_value).css('width', widthComplete + '%');
                this.$('.o_progressbar_complete').toggleClass('o_progress_unacceptable', value < ref_value).css('width', widthComplete + '%');
            }
            else {
                this.$('.o_progressbar_complete').toggleClass('o_progress_acceptable', value < ref_value).css('width', widthComplete + '%');
                this.$('.o_progressbar_complete').toggleClass('o_progress_unacceptable', value > ref_value).css('width', widthComplete + '%');
            }
            this.$('.o_progressbar_complete').css('width', widthComplete + '%');

            if (!this.write_mode) {
                if (max_value !== 100) {
                    this.$('.o_progressbar_value').text(utils.human_number(value) + " / " + utils.human_number(max_value));
                } else {
                    this.$('.o_progressbar_value').text(utils.human_number(value) + "%");
                }
            } else if (isNaN(v)) {
                this.$('.o_progressbar_value').val(this.edit_max_value ? max_value : value);
                this.$('.o_progressbar_value').focus().select();
            }
        }
    });

});