window.__esmOrder.push('l35');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['35'] = { id: 35, name: 'state-35' };
  window.__legacyLayers.view['35'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['35'].id; }
  };
  window.__legacyLayers.controller['35'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['35'].id,
        card: window.__legacyLayers.view['35'].render(),
        label: 'controller-35'
      };
    }
  };
})();
