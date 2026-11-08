# c2.transform.ooxml

[English](README.md)

Office Open XML のファイル（`.docx`・`.xlsx`・`.pptx` などの Word・Excel・PowerPoint のファイル）を、Plone で検索できるようにします。

このアドオンは、`portal_transforms` に transform を 1 つ（`ooxml_to_text`）登録します。Plone の検索（と、`portal_transforms.convertTo("text/plain", ...)` を使うアドオン）が、これらのファイルの文字を取れるようになります。文字は、Python の `zipfile` と lxml だけで読みます。Java・LibreOffice・ほかのサービス・ほかのライブラリは使いません。

取り出すのは文字だけです。文書の構造（見出し・表・配置）は保ちません。

## 受ける形式

| 拡張子 | MIME type |
|---|---|
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.dotx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.template` |
| `.docm` | `application/vnd.ms-word.document.macroEnabled.12` |
| `.dotm` | `application/vnd.ms-word.template.macroEnabled.12` |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `.xltx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.template` |
| `.xlsm` | `application/vnd.ms-excel.sheet.macroEnabled.12` |
| `.xltm` | `application/vnd.ms-excel.template.macroEnabled.12` |
| `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| `.potx` | `application/vnd.openxmlformats-officedocument.presentationml.template` |
| `.ppsx` | `application/vnd.openxmlformats-officedocument.presentationml.slideshow` |
| `.pptm` | `application/vnd.ms-powerpoint.presentation.macroEnabled.12` |
| `.potm` | `application/vnd.ms-powerpoint.template.macroEnabled.12` |
| `.ppsm` | `application/vnd.ms-powerpoint.slideshow.macroEnabled.12` |

ISO/IEC 29500 の Strict の形の文書も読みます。マクロは読まず、動かしません。

受けない物: `.xlsb`（XML ではないバイナリの形式）と、旧の形式の `.doc`・`.xls`・`.ppt`。

## 取り出す文字

| 形式 | 入れる | 入れない |
|---|---|---|
| Word | 本文、表の中、ヘッダーとフッター、脚注と文末脚注、変更履歴で挿入した文字 | コメント、変更履歴で消した文字、フィールドの命令 |
| Excel | シートの名前、セルの値（文字と数値、数式は保存されている結果） | 数式そのもの、コメント、ふりがな |
| PowerPoint | スライドの文字（表と図形の中を含む）、ノート | コメント |

- Word: 本文が先で、その後にヘッダーとフッター、脚注、文末脚注。段落ごとに改行します。タブと改行は保ちます。
- Excel: ブックの中の順のシート（非表示のシートも）。シートごとに、まず名前を 1 行に書き、次に行ごとに、セルの値をタブでつないだ 1 行にします。日付は、保存されている数値のままです。
- PowerPoint: プレゼンテーションの中の順のスライド（非表示のスライドも）と、それぞれのスライドの後にそのノート。段落ごとに改行します。

## 上限とエラー

悪意のあるファイルや壊れたファイルで、Plone が止まったり遅くなったりしないようにします。1 つの文書に、次の上限があります。

| 上限 | 値 |
|---|---|
| 1 つの部品の展開後の大きさ | 64 MiB |
| 読んだ部品の展開後の大きさの合計 | 256 MiB |
| 読む部品の数 | 5,000 |
| 文字の長さ | 10,000,000 文字 |
| 時間 | 30 秒 |

- 大きさは、部品を読みながら数えます。zip が申告する大きさは信じません。
- 上限に当たったら、それまでに読んだ文字を返し、WARNING の log を書きます。
- zip でないファイル（パスワード付きの文書は zip ではありません）・壊れた zip・壊れた XML では、文字は空になり、WARNING の log を書きます。Plone でのファイルの保存は失敗しません。
- XML は、実体・DTD・ネットワークを使わずに読みます。DOCTYPE を持つ部品は読みません。
- log に文書の中身は書きません。

## インストール

プロジェクトの依存に `c2.transform.ooxml` を足し、アドオンの設定の画面で「c2.transform.ooxml」を有効にします。インストールで、サイトがまだ知らない MIME type と、transform を登録します。

**このパッケージと c2.transform.msoffice は、どちらか一方だけを入れてください。** 両方がこれらの MIME type を受けるので、Plone がどちらを使うかが予想しにくくなります。旧の形式（`.doc`・`.xls`・`.ppt`）も要るなら c2.transform.msoffice を、Office Open XML だけでよく Java を入れたくないなら c2.transform.ooxml を選びます。

### すでにあるファイルを索引し直す

インストールでは、サイトにすでにあるファイルを索引し直しません（大きなサイトでは何時間もかかるため）。インストールの後に、次のどちらかで索引し直してください。

- catalog の全体: ZMI の `portal_catalog` の Advanced で「Clear and Rebuild」（`manage_catalogRebuild`）。
- Office Open XML のファイルだけ: 例えば `bin/zconsole run <zope.conf> reindex_ooxml.py` で次を動かします。

  ```python
  from c2.transform.ooxml.config import ooxml_mimetypes
  from zope.component.hooks import setSite

  import transaction

  portal = app.Plone  # サイトの id
  setSite(portal)
  types = [m["mimetypes"][0] for m in ooxml_mimetypes]
  for brain in portal.portal_catalog.unrestrictedSearchResults(mime_type=types):
      brain._unrestrictedGetObject().reindexObject(idxs=["SearchableText"])
  transaction.commit()
  ```

### アンインストール

アドオンの設定の画面で無効にします。transform は消えます。MIME type は、ほかのアドオンが使うかもしれないので残します。

## 対応する版

Plone 6.0・6.1・6.2、Python 3.10〜3.14（Plone 6.0 と 6.1 は Python 3.13 まで）。

## ライセンス

GPL version 2 or later。
