window.__esmOrder.push('l34');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['34'] = { id: 34, name: 'state-34' };
  window.__legacyLayers.view['34'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['34'].id; }
  };
  window.__legacyLayers.controller['34'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['34'].id,
        card: window.__legacyLayers.view['34'].render(),
        label: 'controller-34'
      };
    }
  };
})();
