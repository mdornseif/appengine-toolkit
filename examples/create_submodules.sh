git submodule add git://github.com/kamens/gae_mini_profiler.git lib/gae_mini_profiler
git submodule add https://github.com/mitsuhiko/itsdangerous.git lib/itsdangerous-checkout
git submodule add https://github.com/mdornseif/pagedown-bootstrap.git lib/pagedown-bootstrap
git submodule add git@github.com:mdornseif/huTools.git lib/huTools-checkout
git submodule add git@github.com:hudora/gcs-client.git lib/gcs-client
git submodule add git@github.com:hudora/CentralServices.git lib/CentralServices
git submodule add git@github.com:mdornseif/appengine-toolkit.git lib/appengine-toolkit
git submodule add git@github.com:mdornseif/gaetk_replication.git lib/gaetk_replication
git submodule add git@github.com:mdornseif/gaetk_longtask.git lib/gaetk_longtask
git submodule add https://github.com/wtforms/wtforms.git  lib/simplecodes-wtforms
git submodule add lib/xlwt-checkout https://github.com/python-excel/xlwt.git
git submodule add https://github.com/python-excel/xlwt.git lib/xlwt-checkout
ls -d ./* | sort > submodules.pth
subl submodules.pth 
