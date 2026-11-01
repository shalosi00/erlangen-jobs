const appConfig = {
  'appBaseHref': '/jobsuche/',
  'baseUrl': 'https://www.arbeitsagentur.de/jobsuche/',
  'endpoints__headermodule__host': 'https://web.arbeitsagentur.de',
  'endpoints__headermodule__port': '443',
  'endpoints__headermodule__prefix': '/headerfooter',
  'endpoints__headermodule__resource': '/hf-v7/releases/bahf-webcomponents/bahf-webcomponents.esm.js',
  'endpoints__stellenangebote__host': 'https://rest.arbeitsagentur.de',
  'endpoints__stellenangebote__port': '443',
  'endpoints__stellenangebote__prefix': '/jobboerse/jobsuche-service',
  'endpoints__stellenangebote__resource': '/pc/v6/jobs',

  'endpoints__jobdetails__host': 'https://rest.arbeitsagentur.de',
  'endpoints__jobdetails__port': '443',
  'endpoints__jobdetails__prefix': '/jobboerse/jobsuche-service',
  'endpoints__jobdetails__resource': '/pc/v4/jobdetails',

  'endpoints__kontaktdaten__host': 'https://rest.arbeitsagentur.de',
  'endpoints__kontaktdaten__port': '443',
  'endpoints__kontaktdaten__prefix': '/jobboerse/jobsuche-service',
  'endpoints__kontaktdaten__resource': '/pc/v3/jobs/{jobid}/bewerbung',

  'endpoints__kontaktdatenangemeldet__host': 'https://rest.arbeitsagentur.de',
  'endpoints__kontaktdatenangemeldet__port': '443',
  'endpoints__kontaktdatenangemeldet__prefix': '/jobboerse/jobsuche-service',
  'endpoints__kontaktdatenangemeldet__resource': '/pd/v3/jobs/{jobid}/bewerbung',

  'endpoints__suchauftraege__host': 'https://rest.arbeitsagentur.de',
  'endpoints__suchauftraege__port': '443',
  'endpoints__suchauftraege__prefix': '/jobboerse/jobsuche-service',
  'endpoints__suchauftraege__resource': '/pd/v1/suchauftraege',

  'endpoints__vormerkungen__host': 'https://rest.arbeitsagentur.de',
  'endpoints__vormerkungen__port': '443',
  'endpoints__vormerkungen__prefix': '/jobboerse/jobsuche-service',
  'endpoints__vormerkungen__resource': '/pd/v1/vormerkungen',

  'endpoints__vormerkungenV3__host': 'https://rest.arbeitsagentur.de',
  'endpoints__vormerkungenV3__port': '443',
  'endpoints__vormerkungenV3__prefix': '/jobboerse/jobsuche-service',
  'endpoints__vormerkungenV3__resource': '/pd/v3/vormerkungen',

  'endpoints__stellenmeldung__host': 'https://rest.arbeitsagentur.de',
  'endpoints__stellenmeldung__port': '443',
  'endpoints__stellenmeldung__prefix': '/jobboerse/jobsuche-service',
  'endpoints__stellenmeldung__resource': '/pc/v2/jobs/{jobid}/meldung',

  'endpoints__feedback-vermittlung__host': 'https://rest.arbeitsagentur.de',
  'endpoints__feedback-vermittlung__port': '443',
  'endpoints__feedback-vermittlung__prefix': '/jobboerse/jobsuche-service',
  'endpoints__feedback-vermittlung__resource': '/pc/v1/feedback',
  'endpoints__arbeitgeberdarstellung__host': 'https://rest.arbeitsagentur.de',
  'endpoints__arbeitgeberdarstellung__port': '443',
  'endpoints__arbeitgeberdarstellung__prefix': '/vermittlung/ag-darstellung-service',
  'endpoints__arbeitgeberdarstellung__resource': '/pc/v1/arbeitgeberdarstellung',

  'endpoints__agdmedia__host': 'https://rest.arbeitsagentur.de',
  'endpoints__agdmedia__port': '443',
  'endpoints__agdmedia__prefix': '/vermittlung/ag-darstellung-service',
  'endpoints__agdmedia__resource': '/ct/v1',
  'endpoints__orte__host': 'https://rest.arbeitsagentur.de',
  'endpoints__orte__port': '443',
  'endpoints__orte__prefix': '/jobboerse/kataloge-service',
  'endpoints__orte__resource': '/ed/v2/orte',
  'endpoints__suggest__host': 'https://rest.arbeitsagentur.de',
  'endpoints__suggest__port': '443',
  'endpoints__suggest__prefix': '/jobboerse/suggest-service',
  'endpoints__suggest__resource': '/ed/v2/jobsuche/vorschlaege',
  'endpoints__assignment__host': 'https://rest.arbeitsagentur.de',
  'endpoints__assignment__port': '443',
  'endpoints__assignment__prefix': '/idaas/id-aas-service',
  'endpoints__assignment__resource': '/pc/v1/assignment',

  'endpoints__captcha__host': 'https://rest.arbeitsagentur.de',
  'endpoints__captcha__port': '443',
  'endpoints__captcha__prefix': '/idaas/id-aas-service',
  'endpoints__captcha__resource': '/ct/v1/captcha',

  'aas__protectionlevel': 'JB_JOBSUCHE_20',
  'aas__formId': 'ARBEITGEBERDATEN',
  'endpoints__mapsplace__host': 'https://www.google.com',
  'endpoints__mapsplace__prefix': '/maps/embed/v1',
  'endpoints__mapsplace__resource': '/place?key=AIzaSyDftolzyY9J4R68E3hrk5N-5Cu_QLB54_M',

  'endpoints__mapsdirections__host': 'https://www.google.com',
  'endpoints__mapsdirections__prefix': '/maps/embed/v1',
  'endpoints__mapsdirections__resource': '/directions?key=AIzaSyDftolzyY9J4R68E3hrk5N-5Cu_QLB54_M',

  'endpoints__safarimapsdirections__host': 'https://www.google.com',
  'endpoints__safarimapsdirections__prefix': '/maps/embed/v1',
  'endpoints__safarimapsdirections__resource': '/directions?key=AIzaSyDftolzyY9J4R68E3hrk5N-5Cu_QLB54_M',
  'endpoints__profil__host': 'https://web.arbeitsagentur.de',
  'endpoints__profil__port': '',
  'endpoints__profil__prefix': '/profil',
  'endpoints__profil__resource': '/profil-ui/pd/',

  'agd-ui': 'https://web.arbeitsagentur.de/vermittlung/ag-darstellung-ui',
  'jobsuche-ui': 'https://www.arbeitsagentur.de/jobsuche',
  'jobboerse': 'https://jobboerse.arbeitsagentur.de/vamJB',
  'oidc__clientId': 'jobboerse-jobsuche',
  'oidc__oiamwcuri': 'https://www.arbeitsagentur.de/oiambk/oiam-oauth-wc/v1/oiam-oauth-wc.esm.js',
  'oidc__logouturi': 'https://www.arbeitsagentur.de/jobsuche/',
  'oidc__redirecturi': 'https://www.arbeitsagentur.de/jobsuche/auth-redirect',
  'endpoints__matomo__host': 'https://web.arbeitsagentur.de',
  'endpoints__matomo__prefix': '/analytics',
  'endpoints__matomo__resource': '/tracker/',
  matomo: {
    cookieDomain: '*.arbeitsagentur.de',
    siteId: '35',
    customDimensions: {
      searchId:
{
  id: '1'
}
,
}
}
}
;

window.config = Object.assign({}, window.config || {}, appConfig);