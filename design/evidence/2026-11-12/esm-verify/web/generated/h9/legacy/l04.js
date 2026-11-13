window.__esmOrder.push('l04');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['04'] = { id: 4, name: 'state-04' };
  window.__legacyLayers.view['04'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['04'].id; }
  };
  window.__legacyLayers.controller['04'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['04'].id,
        card: window.__legacyLayers.view['04'].render(),
        label: 'controller-04'
      };
    }
  };
})();
