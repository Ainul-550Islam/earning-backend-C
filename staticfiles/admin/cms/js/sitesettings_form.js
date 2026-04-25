// static/admin/cms/js/sitesettings_form.js
'use strict';

(function() {
    // JSON Preview Update Function
    window.updateJsonPreview = function(dataType) {
        const valueField = document.getElementById('id_value');
        const previewField = document.getElementById('id_json_preview');
        
        if (!valueField || !previewField) return;
        
        try {
            let value = valueField.value;
            
            if (dataType === 'array' || dataType === 'object') {
                if (!value || value.trim() === '') {
                    previewField.value = dataType === 'array' ? '[]' : '{}';
                } else {
                    try {
                        const parsed = JSON.parse(value);
                        previewField.value = JSON.stringify(parsed, null, 2);
                    } catch (e) {
                        previewField.value = value;
                    }
                }
            } else {
                previewField.value = value;
            }
        } catch (e) {
            console.warn('JSON preview update failed:', e);
            previewField.value = valueField.value || '';
        }
    };
    
    // Setup Function
    window.setupSiteSettingsForm = function() {
        const dataTypeField = document.getElementById('id_data_type');
        const valueField = document.getElementById('id_value');
        
        if (!dataTypeField || !valueField) return;
        
        dataTypeField.addEventListener('change', function(e) {
            updateJsonPreview(e.target.value);
        });
        
        valueField.addEventListener('input', function() {
            const dataType = dataTypeField.value || 'string';
            updateJsonPreview(dataType);
        });
        
        valueField.addEventListener('blur', function() {
            const dataType = dataTypeField.value || 'string';
            updateJsonPreview(dataType);
        });
        
        updateJsonPreview(dataTypeField.value || 'string');
    };
    
    // Auto-run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupSiteSettingsForm);
    } else {
        setupSiteSettingsForm();
    }
})();