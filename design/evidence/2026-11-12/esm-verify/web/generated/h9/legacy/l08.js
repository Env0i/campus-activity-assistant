window.__esmOrder.push('l08');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['08'] = { id: 8, name: 'state-08' };
  window.__legacyLayers.view['08'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['08'].id; }
  };
  window.__legacyLayers.controller['08'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['08'].id,
        card: window.__legacyLayers.view['08'].render(),
        label: 'controller-08'
      };
    }
  };
})();
