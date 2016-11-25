#!/bin/sh
mkdir downloads
cd downloads
echo "Downloading CDR data..."
wget http://www.biocreative.org/media/store/files/2016/CDR_Data.zip
echo "Extracting data..."
unzip -qq CDR_Data.zip
echo "Copying data to data directory..."
cd ../
cp downloads/CDR_Data/CDR.Corpus.v010516/CDR_TrainingSet.BioC.xml data/.
cp downloads/CDR_Data/CDR.Corpus.v010516/CDR_DevelopmentSet.BioC.xml data/.
cp downloads/CDR_Data/CDR.Corpus.v010516/CDR_TestSet.BioC.xml data/.
echo "Deleting downloads directory..."
rm -rf downloads
echo "Done!"

