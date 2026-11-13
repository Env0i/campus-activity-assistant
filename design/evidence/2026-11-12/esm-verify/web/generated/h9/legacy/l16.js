window.__esmOrder.push('l16');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['16'] = { id: 16, name: 'state-16' };
  window.__legacyLayers.view['16'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['16'].id; }
  };
  window.__legacyLayers.controller['16'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['16'].id,
        card: window.__legacyLayers.view['16'].render(),
        label: 'controller-16'
      };
    }
  };
})();
