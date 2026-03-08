%%
%
% Read in and plot the submerged Argo float response.
%
clearvars
%
% Use Latex for plotting
%
set(0,'defaulttextinterpreter','latex')
set(groot, 'defaultAxesTickLabelInterpreter','latex'); 
set(groot, 'defaultLegendInterpreter','latex');
% Figure counter
ifig=0;
%
%%
% The WAMIT filenames
%
fname='argo';
gdfname='argo.gdf';
%
% Read the gdf file to get ulen, grav and is(). 
%
[ulen,grav]=textread(gdfname,'%f %f %*s',1,'headerlines',1);
[is(1,1),is(2,1)]=textread(gdfname,'%d %d %*s',1,'headerlines',2);
%
%%
% Read in the added mass and damping coefficients
%
Order='TM'; nh=1;
%
[T,A,B]=ReadWAMIT1file(strcat(fname,'.1'),nh,Order);
%
nf=length(T);
nmodes=length(A(1,:,1));  modes=[1:nmodes];
newmodes=nmodes-6;
%
freqA=1./T; 
%
% Remove the infinite frequency limit if it's there.
%
i0=find(freqA==Inf);freqA(i0)=[]; Ainf=A(i0,:,:); A(i0,:,:)=[]; B(i0,:,:)=[];
%
% Remove the zero frequency value if it's there. 
%
i0=find(freqA<0); freqA(i0)=[];A(i0,:,:)=[]; B(i0,:,:)=[];
om=2*pi*freqA*sqrt(ulen/grav); % Non-dimensional radian frequency vector.
%
disp(['Found ',num2str(nf),' periods in the .1 file.']);
%
%%
% Read the excitation forces
%
clear T;
[betaW,T,Xmag,Xphase,XR,XI]=ReadWAMIT234file(strcat(fname,'.3'),nh,Order);
XjD=XR+1i*XI; 
%
% Save the heading angles and frequencies from this file.
%
nbeta=length(betaW);
nfd=length(T);
freq(1:nfd,1)=1./T; 
omD=2*pi*freq*sqrt(ulen/grav); % Non-dimensional diffraction frequencies
%
%%
% Read in the mass matrix and the hydrostatic coefficients.
%
% The hydrostatic matrix is already non-dimensional.
%
fid=fopen(strcat(fname,'.hst')); clear tmp;
for j=1:nh, fgetl(fid); end % Read 1 header line
[tmp]=fscanf(fid,'%f',3*nmodes^2);
cjk=reshape(tmp(3:3:end),nmodes,nmodes);
fclose(fid);
%
% Read M_ij
%
fid=fopen(strcat(fname,'.mmx')); clear tmp;
for j=1:12+nh, fgetl(fid); end;
% Mij/rho with only 6 modes
[tmp]=fscanf(fid,'%f',3*6^2);
mjk=reshape(tmp(3:3:end),6,6);
%
mjk=mjk/ulen^3; mjk(1:3,4:6)=mjk(1:3,4:6)/ulen;
mjk(4:6,1:3)=mjk(4:6,1:3)/ulen; mjk(4:6,4:6)=mjk(4:6,4:6)/ulen^2;
fclose(fid);
%%
% Solve for the response and confirm that it agrees with the WAMIT results.
%
xi=zeros(6,nfd); ib=1;
for i=1:nfd
    %
    %
    Mat = -omD(i)^2*(mjk+squeeze(A(i,:,:)-1i*B(i,:,:)))+cjk;
    %
    % Note the .' here for just an array transpose NOT a conjugate transpose! 
    %
    xi(:,i)=Mat\XjD(i,:).';
end
%
% Read in the WAMIT RAOs and display the error
%
[betaW,T,Xmag,Xphase,XR,XI]=ReadWAMIT234file(strcat(fname,'.4'),nh,Order);
xiW=XR+1i*XI; 
err=(xi.'-xiW);
disp(['Norm of the error in the response wrt WAMIT: ',num2str(norm(err(:))),...
    ', heading angle \beta=',num2str(betaW(ib))])
%
% Plot the response
%
ifig=ifig+1; figure(ifig); clf
i0=1; 
for m=[1,3,5]
    subplot(1,3,i0);
    plot(T,abs(xi(m,:)))
    xlim([0,20])
    xlabel('$T$ [s]'); grid on; 
    ylabel(['$|\bar\xi_',num2str(m),'|$'])
    i0=i0+1;
end
%%
% The natural frequencies
%
om3=sqrt(cjk(3,3)/(mjk(3,3)+max(A(:,3,3))));
T3=2*pi/om3*sqrt(ulen/grav)
om4=sqrt(cjk(4,4)/(mjk(4,4)+max(A(:,4,4))));
T4=2*pi/om4*sqrt(ulen/grav)

%%
%
% Re set to tex
%
set(0,'defaulttextinterpreter','tex')
set(groot, 'defaultAxesTickLabelInterpreter','tex'); 
set(groot, 'defaultLegendInterpreter','tex');

