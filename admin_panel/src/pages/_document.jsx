import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta charSet="utf-8" />

        <link rel="manifest" href="/site.webmanifest" />

        <meta name="theme-color" content="#141B4D" />
        <meta name="msapplication-TileColor" content="#141B4D" />
        <meta name="apple-mobile-web-app-title" content="PickOrbeet" />
        <meta name="application-name" content="PickOrbeet" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
