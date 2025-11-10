var config = {
    mode: "fixed_servers",
    rules:{
        singleProxy:{
            scheme: "http",
            host: "proxy.dpf.gov.pf",
            port: parseInt(8080)
        },
        bypassList: ["localhost"]
    }
};

chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

function callbackFn(details) {
    return {
        authCredentials: {
            username: "atalaia",
            password: "proj0Talaia992025"
        }
    };
}

chrome.webRequest.onAuthRequired.addListener(
    callbackFn,
    {urls: ["<all_urls>"]},
    ['blocking']
);