window.__esmOrder.push('l26');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['26'] = { id: 26, name: 'state-26' };
  window.__legacyLayers.view['26'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['26'].id; }
  };
  window.__legacyLayers.controller['26'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['26'].id,
        card: window.__legacyLayers.view['26'].render(),
        label: 'controller-26'
      };
    }
  };
})();
